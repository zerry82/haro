from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from typing import TypeVar

import docker

from app.config import settings
from app.models.sandbox_node import SandboxNode

T = TypeVar("T")
_docker_blocked_until = 0.0


class DockerGateway:
    def __init__(self, docker_clients: dict[str, docker.DockerClient] | None = None):
        self._docker_clients: dict[str, docker.DockerClient] = docker_clients or {}

    def get_client(self, node: SandboxNode) -> docker.DockerClient:
        if node.id in self._docker_clients:
            return self._docker_clients[node.id]
        host = node.host
        if host.startswith("unix://") or host == "local":
            client = docker.from_env(timeout=settings.sandbox_docker_timeout)
        else:
            client = docker.DockerClient(base_url=host, timeout=settings.sandbox_docker_timeout)
        self._docker_clients[node.id] = client
        return client

    async def call(self, operation: Callable[[], T], operation_name: str) -> T:
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

    def create_container(self, node: SandboxNode, project_id: str, workspace_path: str):
        return self.get_client(node).containers.run(
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
        )

    def get_container(self, node: SandboxNode, container_id: str):
        return self.get_client(node).containers.get(container_id)

    def remove_container(self, node: SandboxNode, container_id: str) -> None:
        container = self.get_container(node, container_id)
        container.stop(timeout=3)
        container.remove()

    def stop_container(self, node: SandboxNode, container_id: str) -> None:
        container = self.get_container(node, container_id)
        container.stop(timeout=3)

    def start_container(self, node: SandboxNode, container_id: str) -> None:
        container = self.get_container(node, container_id)
        container.start()

    def load_container_status(self, node: SandboxNode, container_id: str) -> str:
        container = self.get_container(node, container_id)
        container.reload()
        return container.status

    def load_container_networks(self, node: SandboxNode, container_id: str) -> dict:
        container = self.get_container(node, container_id)
        container.reload()
        return container.attrs.get("NetworkSettings", {}).get("Networks", {})
