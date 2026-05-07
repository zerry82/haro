from __future__ import annotations

import os

from docker.errors import NotFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.container_db import get_node, record_activity, require_project
from app.services.container_docker import DockerGateway
from app.services.container_lifecycle import ContainerLifecycle
from app.services.container_runtime import build_command, decode_exec_output, validate_workspace_path


class ContainerExecution:
    def __init__(self, db: AsyncSession, docker_gateway: DockerGateway, lifecycle: ContainerLifecycle):
        self.db = db
        self.docker = docker_gateway
        self.lifecycle = lifecycle

    async def execute_code(self, project_id: str, filename: str, code: str, timeout: int | None = None) -> dict:
        if timeout is None:
            timeout = settings.sandbox_exec_timeout

        project = await require_project(self.db, project_id)
        await self.lifecycle.ensure_running(project_id)
        await self.db.refresh(project)

        if project.container_status != "running":
            raise RuntimeError("Sandbox is not running")

        node = await get_node(self.db, project.sandbox_node_id)
        if node is None:
            raise RuntimeError("Sandbox node not found")

        try:
            container = await self.docker.call(
                lambda: self.docker.get_container(node, project.container_id),
                "get_container_for_exec",
            )
        except NotFound as exc:
            raise RuntimeError("Container not found") from exc

        workspace = project.workspace_path
        validate_workspace_path(workspace, filename)
        filepath = os.path.join(workspace, filename)
        os.makedirs(os.path.dirname(filepath) or workspace, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        cmd = build_command(filename)
        try:
            exec_result = await self.docker.call(
                lambda: container.exec_run(cmd, workdir="/workspace", demux=True),
                "execute_code",
            )
            stdout, stderr = decode_exec_output(exec_result.output)
            exit_code = exec_result.exit_code
        except Exception as exc:
            stdout = ""
            stderr = str(exc)
            exit_code = -1

        await record_activity(self.db, project_id)
        return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}
