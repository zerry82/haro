from __future__ import annotations

from datetime import datetime, timezone

from docker.errors import NotFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.container_db import get_node, require_project
from app.services.container_docker import DockerGateway
from app.services.container_lifecycle import ContainerLifecycle


class ContainerDeploy:
    def __init__(self, db: AsyncSession, docker_gateway: DockerGateway, lifecycle: ContainerLifecycle):
        self.db = db
        self.docker = docker_gateway
        self.lifecycle = lifecycle

    async def start_deploy(self, project_id: str) -> str:
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
                "get_container_for_deploy",
            )
        except NotFound as exc:
            raise RuntimeError("Container not found") from exc

        await self.docker.call(
            lambda: container.exec_run(
                ["sh", "-c", "deno run --allow-all --allow-net https://deno.land/std/http/file_server.ts /workspace --port 3000 &"],
                detach=True,
            ),
            "start_file_server",
        )

        project.runtime_mode = "deploy"
        project.last_activity_at = datetime.now(timezone.utc).isoformat()
        await self.db.commit()

        ip = await self.lifecycle.get_container_ip(project_id)
        if not ip:
            raise RuntimeError("Could not determine container IP")
        return ip

    async def start_preview(self, project_id: str) -> str:
        return await self.start_deploy(project_id)

    async def stop_deploy(self, project_id: str) -> None:
        project = await require_project(self.db, project_id)

        project.runtime_mode = "work"
        if project.container_status == "running":
            await self.lifecycle.stop_container(project)
        await self.db.commit()
