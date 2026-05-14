from __future__ import annotations

import json
import logging

from sqlalchemy import select

from app.config import settings
import app.database as db_module
from app.models.sandbox_node import SandboxNode
from app.models.skill import InstalledSkill

logger = logging.getLogger(__name__)

BUILTIN_FILE_OPS_TOOLS = [
    "file_create",
    "file_read",
    "file_stats",
    "file_search_content",
    "file_read_range",
    "file_write",
    "file_edit",
    "file_append",
    "file_replace_range",
    "file_delete",
    "file_move",
    "dir_list",
    "dir_create",
    "dir_delete",
    "file_search",
    "file_count",
    "web_search",
    "mail_search",
    "mail_attachment_read",
]


def builtin_file_ops_manifest() -> dict:
    return {"tools": list(BUILTIN_FILE_OPS_TOOLS)}


async def seed_builtin_skills() -> None:
    async with db_module.async_session_factory() as db:
        result = await db.execute(select(InstalledSkill).where(InstalledSkill.name == "file_ops"))
        existing = result.scalar_one_or_none()
        manifest = builtin_file_ops_manifest()
        if not existing:
            skill = InstalledSkill(
                name="file_ops",
                version="1.0.0",
                type="builtin",
                description="파일 시스템 도구 — 파일/디렉토리 생성, 읽기, 수정, 이동, 삭제, 검색, 개수 조회",
                status="enabled",
                manifest=json.dumps(manifest),
            )
            db.add(skill)
            await db.commit()
            return

        try:
            existing_manifest = json.loads(existing.manifest)
        except Exception:
            existing_manifest = {}
        tools = set(existing_manifest.get("tools", []))
        missing_tools = [tool for tool in BUILTIN_FILE_OPS_TOOLS if tool not in tools]
        if missing_tools:
            existing_manifest["tools"] = [*existing_manifest.get("tools", []), *missing_tools]
            existing.manifest = json.dumps(existing_manifest)
            if existing.description:
                existing.description = "파일 시스템 도구 — 파일/디렉토리 생성, 읽기, 수정, 이동, 삭제, 검색, 개수 조회"
            await db.commit()


async def seed_sandbox_node() -> None:
    """Seed default SandboxNode if none exists."""
    async with db_module.async_session_factory() as db:
        result = await db.execute(select(SandboxNode).limit(1))
        if not result.scalar_one_or_none():
            node = SandboxNode(
                host=settings.sandbox_default_node_host,
                status="active",
                max_containers=settings.sandbox_default_node_max_containers,
                current_containers=0,
            )
            db.add(node)
            await db.commit()
            logger.info("Seeded default sandbox node: %s", settings.sandbox_default_node_host)
