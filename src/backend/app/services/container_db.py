from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.sandbox_node import SandboxNode


async def get_project(db: AsyncSession, project_id: str) -> Project | None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one_or_none()


async def require_project(db: AsyncSession, project_id: str) -> Project:
    project = await get_project(db, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")
    return project


async def get_node(db: AsyncSession, node_id: str | None) -> SandboxNode | None:
    if not node_id:
        return None
    result = await db.execute(select(SandboxNode).where(SandboxNode.id == node_id))
    return result.scalar_one_or_none()


async def select_node(db: AsyncSession) -> SandboxNode:
    result = await db.execute(
        select(SandboxNode)
        .where(SandboxNode.status == "active")
        .where(SandboxNode.current_containers < SandboxNode.max_containers)
        .order_by((SandboxNode.max_containers - SandboxNode.current_containers).desc())
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise RuntimeError("No available sandbox nodes")
    return node


async def record_activity(db: AsyncSession, project_id: str) -> None:
    project = await get_project(db, project_id)
    if project:
        project.last_activity_at = datetime.now(timezone.utc).isoformat()
        await db.commit()
