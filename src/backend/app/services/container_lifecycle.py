from __future__ import annotations

import logging
from datetime import datetime, timezone

from docker.errors import NotFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.services.container_db import get_node, get_project, record_activity, require_project, select_node
from app.services.container_docker import DockerGateway
from app.services.container_runtime import docker_status_to_project_status

logger = logging.getLogger(__name__)


class ContainerLifecycle:
    def __init__(self, db: AsyncSession, docker_gateway: DockerGateway):
        self.db = db
        self.docker = docker_gateway

    async def select_node(self):
        return await select_node(self.db)

    async def create_sandbox(self, project_id: str, workspace_path: str) -> str:
        project = await require_project(self.db, project_id)

        if project.container_id and project.container_status in ("running", "creating"):
            logger.info("Project %s already has container %s", project_id, project.container_id)
            return project.container_id

        node = await select_node(self.db)
        project.container_status = "creating"
        project.sandbox_node_id = node.id
        await self.db.commit()

        try:
            container = await self.docker.call(
                lambda: self.docker.create_container(node, project_id, workspace_path),
                "create_sandbox",
            )

            now = datetime.now(timezone.utc).isoformat()
            project.container_id = container.id
            project.container_status = "running"
            project.last_activity_at = now
            node.current_containers += 1
            await self.db.commit()

            logger.info("Created sandbox for project %s: container=%s, node=%s", project_id, container.id, node.id)
            return container.id

        except Exception as exc:
            logger.error("Failed to create sandbox for project %s: %s", project_id, exc)
            project.container_status = "error"
            project.sandbox_node_id = node.id
            await self.db.commit()
            raise

    async def remove_sandbox(self, project_id: str) -> None:
        project = await get_project(self.db, project_id)
        if project is None:
            return

        container_id = project.container_id
        node = await get_node(self.db, project.sandbox_node_id)

        if container_id and node:
            try:
                await self.docker.call(
                    lambda: self.docker.remove_container(node, container_id),
                    "remove_sandbox",
                )
                logger.info("Removed sandbox container %s for project %s", container_id, project_id)
            except NotFound:
                logger.warning("Container %s already removed", container_id)
            except Exception as exc:
                logger.error("Error removing container %s: %s", container_id, exc)

            if node.current_containers > 0:
                node.current_containers -= 1

        project.container_id = None
        project.sandbox_node_id = None
        project.container_status = "none"
        project.last_activity_at = None
        await self.db.commit()

    async def get_status(self, project_id: str) -> str:
        project = await get_project(self.db, project_id)
        if project is None:
            return "none"

        if not project.container_id or not project.sandbox_node_id:
            return project.container_status

        node = await get_node(self.db, project.sandbox_node_id)
        if node is None:
            return project.container_status

        try:
            actual_status = await self.docker.call(
                lambda: self.docker.load_container_status(node, project.container_id),
                "get_status",
            )
            return docker_status_to_project_status(actual_status)
        except NotFound:
            return "none"
        except Exception:
            return project.container_status

    async def get_container_ip(self, project_id: str) -> str | None:
        project = await get_project(self.db, project_id)
        if project is None or not project.container_id or not project.sandbox_node_id:
            return None

        node = await get_node(self.db, project.sandbox_node_id)
        if node is None:
            return None

        try:
            networks = await self.docker.call(
                lambda: self.docker.load_container_networks(node, project.container_id),
                "get_container_ip",
            )
            for net_info in networks.values():
                ip = net_info.get("IPAddress")
                if ip:
                    return ip
            return None
        except Exception:
            return None

    async def ensure_running(self, project_id: str) -> None:
        project = await require_project(self.db, project_id)

        if project.container_status == "running":
            return

        if not project.container_id or not project.sandbox_node_id:
            await self.create_sandbox(project_id, project.workspace_path)
            return

        node = await get_node(self.db, project.sandbox_node_id)
        if node is None:
            raise RuntimeError("Sandbox node not found")

        try:
            await self.docker.call(
                lambda: self.docker.start_container(node, project.container_id),
                "restart_container",
            )
            project.container_status = "running"
            await record_activity(self.db, project_id)
            logger.info("Restarted container %s for project %s", project.container_id, project_id)
        except NotFound:
            project.container_id = None
            project.container_status = "none"
            await self.db.commit()
            await self.create_sandbox(project_id, project.workspace_path)
        except Exception as exc:
            logger.error("Failed to restart container for project %s: %s", project_id, exc)
            project.container_status = "error"
            await self.db.commit()
            raise RuntimeError(f"Failed to restart sandbox: {exc}") from exc

    async def stop_container(self, project: Project) -> None:
        if not project.container_id or not project.sandbox_node_id:
            return

        node = await get_node(self.db, project.sandbox_node_id)
        if node is None:
            return

        try:
            await self.docker.call(
                lambda: self.docker.stop_container(node, project.container_id),
                "stop_container",
            )
        except NotFound:
            pass
        except Exception as exc:
            logger.error("Error stopping container %s: %s", project.container_id, exc)

        project.container_status = "stopped"
