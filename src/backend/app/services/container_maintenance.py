from __future__ import annotations

import logging
from datetime import datetime, timezone

from docker.errors import NotFound
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.project import Project
from app.models.sandbox_node import SandboxNode
from app.services.container_db import get_node
from app.services.container_docker import DockerGateway
from app.services.container_lifecycle import ContainerLifecycle
from app.services.container_runtime import docker_status_to_project_status, is_project_idle

logger = logging.getLogger(__name__)


class ContainerMaintenance:
    def __init__(self, db: AsyncSession, docker_gateway: DockerGateway, lifecycle: ContainerLifecycle):
        self.db = db
        self.docker = docker_gateway
        self.lifecycle = lifecycle

    async def stop_idle_containers(self, idle_minutes: int | None = None) -> list[str]:
        if idle_minutes is None:
            idle_minutes = settings.sandbox_work_idle_timeout_minutes

        now = datetime.now(timezone.utc)
        stopped: list[str] = []

        result = await self.db.execute(
            select(Project).where(
                Project.container_status == "running",
                Project.runtime_mode != "deploy",
                Project.last_activity_at.isnot(None),
            )
        )
        projects = result.scalars().all()

        for project in projects:
            try:
                if is_project_idle(project.last_activity_at, idle_minutes, now):
                    await self.lifecycle.stop_container(project)
                    stopped.append(project.id)
                    logger.info("Stopped idle container for project %s", project.id)
            except Exception as exc:
                logger.error("Error checking idle for project %s: %s", project.id, exc)

        if stopped:
            await self.db.commit()
        return stopped

    async def stop_all(self) -> None:
        result = await self.db.execute(select(Project).where(Project.container_status == "running"))
        projects = result.scalars().all()

        for project in projects:
            try:
                await self.lifecycle.stop_container(project)
            except Exception as exc:
                logger.error("Error stopping container for project %s: %s", project.id, exc)

        await self.db.commit()
        logger.info("Stopped all managed containers (%s total)", len(projects))

    async def reconcile(self) -> None:
        result = await self.db.execute(select(Project).where(Project.container_id.isnot(None)))
        projects = result.scalars().all()

        for project in projects:
            if not project.sandbox_node_id:
                continue

            node = await get_node(self.db, project.sandbox_node_id)
            if node is None:
                project.container_status = "error"
                project.container_id = None
                project.sandbox_node_id = None
                continue

            await self._reconcile_project(project, node)

        await self.db.commit()
        logger.info("Reconciliation complete")

    async def _reconcile_project(self, project: Project, node: SandboxNode) -> None:
        try:
            actual = await self.docker.call(
                lambda: self.docker.load_container_status(node, project.container_id),
                "reconcile_container",
            )
            project.container_status = docker_status_to_project_status(actual)
        except NotFound:
            logger.warning("Container %s not found during reconcile, clearing DB", project.container_id)
            project.container_id = None
            project.container_status = "none"
            project.sandbox_node_id = None
            if node.current_containers > 0:
                node.current_containers -= 1
        except Exception as exc:
            logger.error("Error reconciling project %s: %s", project.id, exc)
