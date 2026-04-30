"""Docker 컨테이너 기반 샌드박스 매니저 (DB 기반 오케스트레이션, 원격 노드 지원)"""
from __future__ import annotations

import logging
import os
import asyncio
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TypeVar

import docker
from docker.errors import APIError, NotFound
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.sandbox_node import SandboxNode
from app.models.project import Project

logger = logging.getLogger(__name__)

T = TypeVar("T")
_docker_blocked_until = 0.0


def validate_workspace_path(workspace: str, requested: str) -> str:
    """Validate that requested path stays within workspace. Raises PermissionError on escape."""
    full = os.path.realpath(os.path.join(workspace, requested.lstrip("/")))
    if not full.startswith(os.path.realpath(workspace)):
        raise PermissionError("Path traversal denied: outside workspace")
    return full


class ContainerManager:
    """Docker 컨테이너 기반 샌드박스 매니저 (원격 노드 지원)"""

    def __init__(self, db_session: AsyncSession, docker_clients: dict[str, docker.DockerClient] | None = None):
        self.db = db_session
        self._docker_clients: dict[str, docker.DockerClient] = docker_clients or {}

    def _get_docker_client(self, node: SandboxNode) -> docker.DockerClient:
        if node.id in self._docker_clients:
            return self._docker_clients[node.id]
        host = node.host
        if host.startswith("unix://") or host == "local":
            client = docker.from_env(timeout=settings.sandbox_docker_timeout)
        else:
            client = docker.DockerClient(base_url=host, timeout=settings.sandbox_docker_timeout)
        self._docker_clients[node.id] = client
        return client

    async def _docker_call(self, operation: Callable[[], T], operation_name: str) -> T:
        """Run blocking Docker SDK calls outside the FastAPI event loop."""
        global _docker_blocked_until

        now = time.monotonic()
        if now < _docker_blocked_until:
            remaining = int(_docker_blocked_until - now)
            raise RuntimeError(f"Docker unavailable; retry after {remaining}s")

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(operation),
                timeout=settings.sandbox_docker_timeout,
            )
        except asyncio.TimeoutError as exc:
            _docker_blocked_until = time.monotonic() + settings.sandbox_docker_circuit_breaker_seconds
            raise RuntimeError(f"Docker {operation_name} timed out") from exc
        except Exception:
            raise

    async def select_node(self) -> SandboxNode:
        result = await self.db.execute(
            select(SandboxNode)
            .where(SandboxNode.status == "active")
            .where(SandboxNode.current_containers < SandboxNode.max_containers)
            .order_by((SandboxNode.max_containers - SandboxNode.current_containers).desc())
        )
        node = result.scalar_one_or_none()
        if node is None:
            raise RuntimeError("No available sandbox nodes")
        return node

    async def create_sandbox(self, project_id: str, workspace_path: str) -> str:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        if project.container_id and project.container_status in ("running", "creating"):
            logger.info(f"Project {project_id} already has container {project.container_id}")
            return project.container_id

        node = await self.select_node()
        project.container_status = "creating"
        project.sandbox_node_id = node.id
        await self.db.commit()

        try:
            container = await self._docker_call(
                lambda: self._get_docker_client(node).containers.run(
                    settings.sandbox_image,
                    command="sleep infinity",
                    detach=True,
                    name=f"sandbox-{project_id[:12]}",
                    mem_limit=settings.sandbox_mem_limit,
                    cpu_period=settings.sandbox_cpu_period,
                    cpu_quota=settings.sandbox_cpu_quota,
                    volumes={os.path.abspath(workspace_path): {"bind": "/workspace", "mode": "rw"}},
                    working_dir="/workspace",
                    labels={"sandbox": "true", "project": project_id},
                ),
                "create_sandbox",
            )

            now = datetime.now(timezone.utc).isoformat()
            project.container_id = container.id
            project.container_status = "running"
            project.last_activity_at = now
            node.current_containers += 1
            await self.db.commit()

            logger.info(f"Created sandbox for project {project_id}: container={container.id}, node={node.id}")
            return container.id

        except Exception as e:
            logger.error(f"Failed to create sandbox for project {project_id}: {e}")
            project.container_status = "error"
            project.sandbox_node_id = node.id
            await self.db.commit()
            raise

    async def remove_sandbox(self, project_id: str) -> None:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            return

        container_id = project.container_id
        node_id = project.sandbox_node_id

        if container_id and node_id:
            node_result = await self.db.execute(
                select(SandboxNode).where(SandboxNode.id == node_id)
            )
            node = node_result.scalar_one_or_none()

            if node:
                try:
                    await self._docker_call(
                        lambda: self._remove_container(node, container_id),
                        "remove_sandbox",
                    )
                    logger.info(f"Removed sandbox container {container_id} for project {project_id}")
                except NotFound:
                    logger.warning(f"Container {container_id} already removed")
                except Exception as e:
                    logger.error(f"Error removing container {container_id}: {e}")

                if node.current_containers > 0:
                    node.current_containers -= 1

        project.container_id = None
        project.sandbox_node_id = None
        project.container_status = "none"
        project.last_activity_at = None
        await self.db.commit()

    @staticmethod
    def build_command(filename: str) -> list[str]:
        if filename.endswith(".ts") or filename.endswith(".js"):
            return ["deno", "run", "--allow-all", f"/workspace/{filename}"]
        elif filename.endswith(".py"):
            return ["python3", f"/workspace/{filename}"]
        else:
            return ["cat", f"/workspace/{filename}"]

    async def execute_code(self, project_id: str, filename: str, code: str, timeout: int | None = None) -> dict:
        if timeout is None:
            timeout = settings.sandbox_exec_timeout

        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        await self.ensure_running(project_id)
        await self.db.refresh(project)

        if project.container_status != "running":
            raise RuntimeError("Sandbox is not running")

        node_result = await self.db.execute(
            select(SandboxNode).where(SandboxNode.id == project.sandbox_node_id)
        )
        node = node_result.scalar_one()
        try:
            container = await self._docker_call(
                lambda: self._get_docker_client(node).containers.get(project.container_id),
                "get_container_for_exec",
            )
        except NotFound:
            raise RuntimeError("Container not found")

        workspace = project.workspace_path
        validate_workspace_path(workspace, filename)
        filepath = os.path.join(workspace, filename)
        os.makedirs(os.path.dirname(filepath) or workspace, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        cmd = self.build_command(filename)
        try:
            exec_result = await self._docker_call(
                lambda: container.exec_run(cmd, workdir="/workspace", demux=True),
                "execute_code",
            )
            stdout_bytes = exec_result.output[0] if exec_result.output[0] else b""
            stderr_bytes = exec_result.output[1] if exec_result.output[1] else b""
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = exec_result.exit_code
        except Exception as e:
            stdout = ""
            stderr = str(e)
            exit_code = -1

        await self._record_activity(project_id)
        return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}

    async def get_status(self, project_id: str) -> str:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            return "none"

        if not project.container_id or not project.sandbox_node_id:
            return project.container_status

        node_result = await self.db.execute(
            select(SandboxNode).where(SandboxNode.id == project.sandbox_node_id)
        )
        node = node_result.scalar_one_or_none()
        if node is None:
            return project.container_status

        try:
            actual_status = await self._docker_call(
                lambda: self._load_container_status(node, project.container_id),
                "get_status",
            )
            if actual_status == "running":
                return "running"
            elif actual_status in ("exited", "dead"):
                return "stopped"
            else:
                return actual_status
        except NotFound:
            return "none"
        except Exception:
            return project.container_status

    async def get_container_ip(self, project_id: str) -> str | None:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None or not project.container_id or not project.sandbox_node_id:
            return None

        node_result = await self.db.execute(
            select(SandboxNode).where(SandboxNode.id == project.sandbox_node_id)
        )
        node = node_result.scalar_one_or_none()
        if node is None:
            return None

        try:
            networks = await self._docker_call(
                lambda: self._load_container_networks(node, project.container_id),
                "get_container_ip",
            )
            for net_name, net_info in networks.items():
                ip = net_info.get("IPAddress")
                if ip:
                    return ip
            return None
        except Exception:
            return None

    async def ensure_running(self, project_id: str) -> None:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        if project.container_status == "running":
            return

        if not project.container_id or not project.sandbox_node_id:
            await self.create_sandbox(project_id, project.workspace_path)
            return

        node_result = await self.db.execute(
            select(SandboxNode).where(SandboxNode.id == project.sandbox_node_id)
        )
        node = node_result.scalar_one_or_none()
        if node is None:
            raise RuntimeError("Sandbox node not found")

        try:
            await self._docker_call(
                lambda: self._start_container(node, project.container_id),
                "restart_container",
            )
            project.container_status = "running"
            await self._record_activity(project_id)
            logger.info(f"Restarted container {project.container_id} for project {project_id}")
        except NotFound:
            project.container_id = None
            project.container_status = "none"
            await self.db.commit()
            await self.create_sandbox(project_id, project.workspace_path)
        except Exception as e:
            logger.error(f"Failed to restart container for project {project_id}: {e}")
            project.container_status = "error"
            await self.db.commit()
            raise RuntimeError(f"Failed to restart sandbox: {e}")

    async def start_deploy(self, project_id: str) -> str:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        await self.ensure_running(project_id)
        await self.db.refresh(project)

        if project.container_status != "running":
            raise RuntimeError("Sandbox is not running")

        node_result = await self.db.execute(
            select(SandboxNode).where(SandboxNode.id == project.sandbox_node_id)
        )
        node = node_result.scalar_one()
        try:
            container = await self._docker_call(
                lambda: self._get_docker_client(node).containers.get(project.container_id),
                "get_container_for_deploy",
            )
        except NotFound:
            raise RuntimeError("Container not found")

        await self._docker_call(
            lambda: container.exec_run(
                ["sh", "-c", "deno run --allow-all --allow-net https://deno.land/std/http/file_server.ts /workspace --port 3000 &"],
                detach=True,
            ),
            "start_file_server",
        )

        project.runtime_mode = "deploy"
        project.last_activity_at = datetime.now(timezone.utc).isoformat()
        await self.db.commit()

        ip = await self.get_container_ip(project_id)
        if not ip:
            raise RuntimeError("Could not determine container IP")
        return ip

    async def start_preview(self, project_id: str) -> str:
        return await self.start_deploy(project_id)

    async def stop_deploy(self, project_id: str) -> None:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        project.runtime_mode = "work"
        if project.container_status == "running":
            await self._stop_container(project)
        await self.db.commit()

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
                last_activity = datetime.fromisoformat(project.last_activity_at)
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)
                elapsed = (now - last_activity).total_seconds() / 60
                if elapsed >= idle_minutes:
                    await self._stop_container(project)
                    stopped.append(project.id)
                    logger.info(f"Stopped idle container for project {project.id} (idle {elapsed:.0f}min)")
            except Exception as e:
                logger.error(f"Error checking idle for project {project.id}: {e}")

        if stopped:
            await self.db.commit()
        return stopped

    async def _stop_container(self, project: Project) -> None:
        if not project.container_id or not project.sandbox_node_id:
            return

        node_result = await self.db.execute(
            select(SandboxNode).where(SandboxNode.id == project.sandbox_node_id)
        )
        node = node_result.scalar_one_or_none()
        if node is None:
            return

        try:
            await self._docker_call(
                lambda: self._stop_container_sync(node, project.container_id),
                "stop_container",
            )
        except NotFound:
            pass
        except Exception as e:
            logger.error(f"Error stopping container {project.container_id}: {e}")

        project.container_status = "stopped"

    async def stop_all(self) -> None:
        result = await self.db.execute(
            select(Project).where(Project.container_status == "running")
        )
        projects = result.scalars().all()

        for project in projects:
            try:
                await self._stop_container(project)
            except Exception as e:
                logger.error(f"Error stopping container for project {project.id}: {e}")

        await self.db.commit()
        logger.info(f"Stopped all managed containers ({len(projects)} total)")

    async def reconcile(self) -> None:
        result = await self.db.execute(
            select(Project).where(Project.container_id.isnot(None))
        )
        projects = result.scalars().all()

        for project in projects:
            if not project.sandbox_node_id:
                continue

            node_result = await self.db.execute(
                select(SandboxNode).where(SandboxNode.id == project.sandbox_node_id)
            )
            node = node_result.scalar_one_or_none()
            if node is None:
                project.container_status = "error"
                project.container_id = None
                project.sandbox_node_id = None
                continue

            try:
                actual = await self._docker_call(
                    lambda: self._load_container_status(node, project.container_id),
                    "reconcile_container",
                )
                if actual == "running":
                    project.container_status = "running"
                elif actual in ("exited", "dead"):
                    project.container_status = "stopped"
                else:
                    project.container_status = actual
            except NotFound:
                logger.warning(f"Container {project.container_id} not found during reconcile, clearing DB")
                project.container_id = None
                project.container_status = "none"
                project.sandbox_node_id = None
                if node.current_containers > 0:
                    node.current_containers -= 1
            except Exception as e:
                logger.error(f"Error reconciling project {project.id}: {e}")

        await self.db.commit()
        logger.info("Reconciliation complete")

    async def _record_activity(self, project_id: str) -> None:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project:
            project.last_activity_at = datetime.now(timezone.utc).isoformat()
            await self.db.commit()

    def _remove_container(self, node: SandboxNode, container_id: str) -> None:
        container = self._get_docker_client(node).containers.get(container_id)
        container.stop(timeout=3)
        container.remove()

    def _stop_container_sync(self, node: SandboxNode, container_id: str) -> None:
        container = self._get_docker_client(node).containers.get(container_id)
        container.stop(timeout=3)

    def _start_container(self, node: SandboxNode, container_id: str) -> None:
        container = self._get_docker_client(node).containers.get(container_id)
        container.start()

    def _load_container_status(self, node: SandboxNode, container_id: str) -> str:
        container = self._get_docker_client(node).containers.get(container_id)
        container.reload()
        return container.status

    def _load_container_networks(self, node: SandboxNode, container_id: str) -> dict:
        container = self._get_docker_client(node).containers.get(container_id)
        container.reload()
        return container.attrs.get("NetworkSettings", {}).get("Networks", {})
