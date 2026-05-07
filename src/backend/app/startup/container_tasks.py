from __future__ import annotations

import asyncio
import logging

from app.config import settings
import app.database as db_module

logger = logging.getLogger(__name__)


async def idle_cleanup_loop() -> None:
    """Background task: periodically stop idle containers."""
    from app.services.container_manager import ContainerManager

    while True:
        try:
            await asyncio.sleep(300)
            async with db_module.async_session_factory() as db:
                cm = ContainerManager(db)
                stopped = await cm.stop_idle_containers()
                if stopped:
                    logger.info("Idle cleanup: stopped %s containers", len(stopped))
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Idle cleanup error: %s", exc)


async def mark_work_containers_stopped_on_startup() -> None:
    """DB-only startup normalization so stale work-mode containers do not look active."""
    from sqlalchemy import text

    try:
        async with db_module.engine.begin() as conn:
            await conn.execute(text("""
                UPDATE projects
                SET container_status = 'stopped'
                WHERE runtime_mode != 'deploy'
                  AND container_status IN ('running', 'creating')
                  AND container_id IS NOT NULL
            """))
    except Exception as exc:
        logger.warning("Could not normalize sandbox status on startup: %s", exc)


async def reconcile_containers() -> None:
    """Reconcile DB state with actual Docker containers on startup."""
    from app.database import async_session_factory
    from app.services.container_manager import ContainerManager

    try:
        async with async_session_factory() as db:
            cm = ContainerManager(db)
            await cm.reconcile()
    except Exception as exc:
        logger.warning("Container reconciliation failed (Docker may not be available): %s", exc)


async def stop_all_containers() -> None:
    """Stop all managed containers on shutdown."""
    from app.database import async_session_factory
    from app.services.container_manager import ContainerManager

    try:
        async with async_session_factory() as db:
            cm = ContainerManager(db)
            await cm.stop_all()
    except Exception as exc:
        logger.warning("Failed to stop containers on shutdown: %s", exc)
