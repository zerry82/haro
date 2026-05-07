"""Docker 컨테이너 기반 샌드박스 매니저 (DB 기반 오케스트레이션, 원격 노드 지원)"""
from __future__ import annotations

import docker
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.sandbox_node import SandboxNode
from app.services.container_db import record_activity
from app.services.container_deploy import ContainerDeploy
from app.services.container_docker import DockerGateway
from app.services.container_execution import ContainerExecution
from app.services.container_lifecycle import ContainerLifecycle
from app.services.container_maintenance import ContainerMaintenance
from app.services.container_runtime import build_command, validate_workspace_path


class ContainerManager:
    """Facade for Docker sandbox lifecycle, execution, deploy, and maintenance."""

    build_command = staticmethod(build_command)

    def __init__(self, db_session: AsyncSession, docker_clients: dict[str, docker.DockerClient] | None = None):
        self.db = db_session
        self.docker = DockerGateway(docker_clients)
        self.lifecycle = ContainerLifecycle(db_session, self.docker)
        self.execution = ContainerExecution(db_session, self.docker, self.lifecycle)
        self.deploy = ContainerDeploy(db_session, self.docker, self.lifecycle)
        self.maintenance = ContainerMaintenance(db_session, self.docker, self.lifecycle)

    def _get_docker_client(self, node: SandboxNode) -> docker.DockerClient:
        return self.docker.get_client(node)

    async def _docker_call(self, operation, operation_name: str):
        return await self.docker.call(operation, operation_name)

    async def select_node(self) -> SandboxNode:
        return await self.lifecycle.select_node()

    async def create_sandbox(self, project_id: str, workspace_path: str) -> str:
        return await self.lifecycle.create_sandbox(project_id, workspace_path)

    async def remove_sandbox(self, project_id: str) -> None:
        await self.lifecycle.remove_sandbox(project_id)

    async def execute_code(self, project_id: str, filename: str, code: str, timeout: int | None = None) -> dict:
        return await self.execution.execute_code(project_id, filename, code, timeout)

    async def get_status(self, project_id: str) -> str:
        return await self.lifecycle.get_status(project_id)

    async def get_container_ip(self, project_id: str) -> str | None:
        return await self.lifecycle.get_container_ip(project_id)

    async def ensure_running(self, project_id: str) -> None:
        await self.lifecycle.ensure_running(project_id)

    async def start_deploy(self, project_id: str) -> str:
        return await self.deploy.start_deploy(project_id)

    async def start_preview(self, project_id: str) -> str:
        return await self.deploy.start_preview(project_id)

    async def stop_deploy(self, project_id: str) -> None:
        await self.deploy.stop_deploy(project_id)

    async def stop_idle_containers(self, idle_minutes: int | None = None) -> list[str]:
        return await self.maintenance.stop_idle_containers(idle_minutes)

    async def _stop_container(self, project: Project) -> None:
        await self.lifecycle.stop_container(project)

    async def stop_all(self) -> None:
        await self.maintenance.stop_all()

    async def reconcile(self) -> None:
        await self.maintenance.reconcile()

    async def _record_activity(self, project_id: str) -> None:
        await record_activity(self.db, project_id)

    def _remove_container(self, node: SandboxNode, container_id: str) -> None:
        self.docker.remove_container(node, container_id)

    def _stop_container_sync(self, node: SandboxNode, container_id: str) -> None:
        self.docker.stop_container(node, container_id)

    def _start_container(self, node: SandboxNode, container_id: str) -> None:
        self.docker.start_container(node, container_id)

    def _load_container_status(self, node: SandboxNode, container_id: str) -> str:
        return self.docker.load_container_status(node, container_id)

    def _load_container_networks(self, node: SandboxNode, container_id: str) -> dict:
        return self.docker.load_container_networks(node, container_id)
