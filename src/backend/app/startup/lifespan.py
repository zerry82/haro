from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import Base, init_db
import app.database as db_module
from app.startup.container_tasks import (
    idle_cleanup_loop,
    mark_work_containers_stopped_on_startup,
    stop_all_containers,
)
from app.startup.migrations import (
    migrate_chat_session_columns,
    migrate_project_columns,
    migrate_session_columns,
    migrate_sessions_to_projects,
)
from app.startup.seeds import seed_builtin_skills, seed_sandbox_node

logger = logging.getLogger(__name__)

_idle_cleanup_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _idle_cleanup_task

    init_db()
    os.makedirs(settings.workspace_root, exist_ok=True)
    async with db_module.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await migrate_session_columns()
    await migrate_project_columns()
    await migrate_chat_session_columns()
    await migrate_sessions_to_projects()
    await seed_builtin_skills()
    await seed_sandbox_node()
    await mark_work_containers_stopped_on_startup()

    _idle_cleanup_task = asyncio.create_task(idle_cleanup_loop())

    yield

    if _idle_cleanup_task:
        _idle_cleanup_task.cancel()
        try:
            await _idle_cleanup_task
        except asyncio.CancelledError:
            pass

    if settings.sandbox_stop_containers_on_shutdown:
        try:
            await asyncio.wait_for(
                stop_all_containers(),
                timeout=max(settings.sandbox_docker_timeout + 2, 5),
            )
        except asyncio.TimeoutError:
            logger.warning("Timed out while stopping Docker containers during shutdown")
    else:
        logger.info("Skipping Docker container stop on shutdown")
