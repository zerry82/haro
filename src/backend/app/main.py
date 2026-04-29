from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, init_db
import app.database as db_module
from app.routers import auth, files, logs, messages, sessions, skills
from app.routers import preview, projects, chats

logger = logging.getLogger(__name__)

# Background task handle for idle cleanup
_idle_cleanup_task: asyncio.Task | None = None


async def _idle_cleanup_loop():
    """Background task: periodically stop idle containers."""
    from app.services.container_manager import ContainerManager
    while True:
        try:
            await asyncio.sleep(300)  # every 5 minutes
            async with db_module.async_session_factory() as db:
                cm = ContainerManager(db)
                stopped = await cm.stop_idle_containers()
                if stopped:
                    logger.info(f"Idle cleanup: stopped {len(stopped)} containers")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Idle cleanup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _idle_cleanup_task

    # Startup
    init_db()
    os.makedirs(settings.workspace_root, exist_ok=True)
    async with db_module.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Migrate: add new columns to sessions table if missing
    await _migrate_session_columns()

    # Migrate: add new columns to projects table if missing
    await _migrate_project_columns()

    # Migrate: sessions → projects + chat_sessions
    await _migrate_sessions_to_projects()

    # Seed builtin skill
    await _seed_builtin_skills()

    # Seed default sandbox node + reconcile
    await _seed_sandbox_node()
    await _reconcile_containers()

    # Start idle cleanup background task
    _idle_cleanup_task = asyncio.create_task(_idle_cleanup_loop())

    yield

    # Shutdown
    if _idle_cleanup_task:
        _idle_cleanup_task.cancel()
        try:
            await _idle_cleanup_task
        except asyncio.CancelledError:
            pass

    await _stop_all_containers()


async def _migrate_session_columns():
    """Add sandbox columns to sessions table if they don't exist (SQLite migration)."""
    from sqlalchemy import text
    async with db_module.engine.begin() as conn:
        # Check existing columns
        result = await conn.execute(text("PRAGMA table_info(sessions)"))
        existing_cols = {row[1] for row in result.fetchall()}

        migrations = [
            ("sandbox_node_id", "ALTER TABLE sessions ADD COLUMN sandbox_node_id VARCHAR(36)"),
            ("container_id", "ALTER TABLE sessions ADD COLUMN container_id VARCHAR(100)"),
            ("container_status", "ALTER TABLE sessions ADD COLUMN container_status VARCHAR(20) DEFAULT 'none' NOT NULL"),
            ("last_activity_at", "ALTER TABLE sessions ADD COLUMN last_activity_at VARCHAR(50)"),
        ]
        for col_name, sql in migrations:
            if col_name not in existing_cols:
                try:
                    await conn.execute(text(sql))
                    logger.info(f"Added column {col_name} to sessions table")
                except Exception as e:
                    logger.warning(f"Could not add column {col_name}: {e}")


async def _migrate_project_columns():
    """Add project columns introduced after the POC schema was created."""
    from sqlalchemy import text
    async with db_module.engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(projects)"))
        existing_cols = {row[1] for row in result.fetchall()}

        migrations = [
            ("runtime_mode", "ALTER TABLE projects ADD COLUMN runtime_mode VARCHAR(20) DEFAULT 'work' NOT NULL"),
        ]
        for col_name, sql in migrations:
            if col_name not in existing_cols:
                try:
                    await conn.execute(text(sql))
                    logger.info(f"Added column {col_name} to projects table")
                except Exception as e:
                    logger.warning(f"Could not add project column {col_name}: {e}")


async def _migrate_sessions_to_projects():
    """Migrate existing sessions data to projects + chat_sessions tables.
    
    Idempotent: skips if projects table already has data.
    Adds chat_session_id columns to messages and agent_logs if missing.
    Also makes session_id nullable in messages and agent_logs (SQLite table rebuild).
    """
    from sqlalchemy import text
    async with db_module.engine.begin() as conn:
        # --- Fix messages table: make session_id nullable + add chat_session_id ---
        result = await conn.execute(text("PRAGMA table_info(messages)"))
        msg_cols = {row[1]: row for row in result.fetchall()}
        
        needs_messages_rebuild = False
        if "chat_session_id" not in msg_cols:
            needs_messages_rebuild = True
        # Check if session_id is NOT NULL (notnull flag is index 3 in PRAGMA result)
        if "session_id" in msg_cols and msg_cols["session_id"][3] == 1:
            needs_messages_rebuild = True
        
        if needs_messages_rebuild:
            try:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS messages_new (
                        id VARCHAR(36) PRIMARY KEY,
                        chat_session_id VARCHAR(36),
                        session_id VARCHAR(36),
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        metadata TEXT,
                        parent_message_id VARCHAR(36),
                        compressed BOOLEAN NOT NULL DEFAULT 0,
                        created_at VARCHAR(50)
                    )
                """))
                # Copy data
                if "chat_session_id" in msg_cols:
                    await conn.execute(text("""
                        INSERT OR IGNORE INTO messages_new 
                        SELECT id, chat_session_id, session_id, role, content, metadata, parent_message_id, compressed, created_at
                        FROM messages
                    """))
                else:
                    await conn.execute(text("""
                        INSERT OR IGNORE INTO messages_new (id, session_id, role, content, metadata, parent_message_id, compressed, created_at)
                        SELECT id, session_id, role, content, metadata, parent_message_id, compressed, created_at
                        FROM messages
                    """))
                await conn.execute(text("DROP TABLE messages"))
                await conn.execute(text("ALTER TABLE messages_new RENAME TO messages"))
                logger.info("Rebuilt messages table with nullable session_id + chat_session_id")
            except Exception as e:
                logger.warning(f"Could not rebuild messages table: {e}")

        # --- Fix agent_logs table: make session_id nullable + add chat_session_id ---
        result = await conn.execute(text("PRAGMA table_info(agent_logs)"))
        log_cols = {row[1]: row for row in result.fetchall()}
        
        needs_logs_rebuild = False
        if "chat_session_id" not in log_cols:
            needs_logs_rebuild = True
        if "session_id" in log_cols and log_cols["session_id"][3] == 1:
            needs_logs_rebuild = True
        
        if needs_logs_rebuild:
            try:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS agent_logs_new (
                        id VARCHAR(36) PRIMARY KEY,
                        chat_session_id VARCHAR(36),
                        session_id VARCHAR(36),
                        round_index INTEGER NOT NULL,
                        event_type VARCHAR(30) NOT NULL,
                        content TEXT NOT NULL,
                        duration_ms FLOAT,
                        created_at VARCHAR(50)
                    )
                """))
                if "chat_session_id" in log_cols:
                    await conn.execute(text("""
                        INSERT OR IGNORE INTO agent_logs_new
                        SELECT id, chat_session_id, session_id, round_index, event_type, content, duration_ms, created_at
                        FROM agent_logs
                    """))
                else:
                    await conn.execute(text("""
                        INSERT OR IGNORE INTO agent_logs_new (id, session_id, round_index, event_type, content, duration_ms, created_at)
                        SELECT id, session_id, round_index, event_type, content, duration_ms, created_at
                        FROM agent_logs
                    """))
                await conn.execute(text("DROP TABLE agent_logs"))
                await conn.execute(text("ALTER TABLE agent_logs_new RENAME TO agent_logs"))
                logger.info("Rebuilt agent_logs table with nullable session_id + chat_session_id")
            except Exception as e:
                logger.warning(f"Could not rebuild agent_logs table: {e}")

        # Check if sessions table exists and has data
        try:
            result = await conn.execute(text("SELECT COUNT(*) FROM sessions"))
            session_count = result.scalar()
        except Exception:
            session_count = 0

        if session_count == 0:
            logger.info("No sessions to migrate")
            return

        # Check if projects already have data (idempotent)
        try:
            result = await conn.execute(text("SELECT COUNT(*) FROM projects"))
            project_count = result.scalar()
            if project_count > 0:
                logger.info("Projects table already has data, skipping migration")
                return
        except Exception:
            pass

        # Migrate sessions → projects + chat_sessions
        logger.info(f"Migrating {session_count} sessions to projects + chat_sessions...")
        result = await conn.execute(text("SELECT * FROM sessions"))
        sessions = result.fetchall()
        columns = result.keys()

        import uuid
        from datetime import datetime, timezone

        for row in sessions:
            row_dict = dict(zip(columns, row))
            session_id = row_dict["id"]
            chat_session_id = str(uuid.uuid4())

            # Create project record with same ID as session
            await conn.execute(text(
                "INSERT INTO projects (id, user_id, title, status, runtime_mode, workspace_path, "
                "sandbox_node_id, container_id, container_status, last_activity_at, "
                "created_at, updated_at) VALUES (:id, :user_id, :title, :status, :runtime_mode, "
                ":workspace_path, :sandbox_node_id, :container_id, :container_status, "
                ":last_activity_at, :created_at, :updated_at)"
            ), {
                "id": session_id,
                "user_id": row_dict["user_id"],
                "title": row_dict["title"],
                "status": row_dict.get("status", "idle"),
                "runtime_mode": "work",
                "workspace_path": row_dict["workspace_path"],
                "sandbox_node_id": row_dict.get("sandbox_node_id"),
                "container_id": row_dict.get("container_id"),
                "container_status": row_dict.get("container_status", "none"),
                "last_activity_at": row_dict.get("last_activity_at"),
                "created_at": row_dict["created_at"],
                "updated_at": row_dict["updated_at"],
            })

            # Create chat_session record
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(text(
                "INSERT INTO chat_sessions (id, project_id, title, created_at, updated_at) "
                "VALUES (:id, :project_id, :title, :created_at, :updated_at)"
            ), {
                "id": chat_session_id,
                "project_id": session_id,
                "title": "기본 채팅",
                "created_at": now,
                "updated_at": now,
            })

            # Map messages.session_id → messages.chat_session_id
            await conn.execute(text(
                "UPDATE messages SET chat_session_id = :chat_session_id "
                "WHERE session_id = :session_id"
            ), {"chat_session_id": chat_session_id, "session_id": session_id})

            # Map agent_logs.session_id → agent_logs.chat_session_id
            await conn.execute(text(
                "UPDATE agent_logs SET chat_session_id = :chat_session_id "
                "WHERE session_id = :session_id"
            ), {"chat_session_id": chat_session_id, "session_id": session_id})

            logger.info(f"Migrated session {session_id} → project + chat_session {chat_session_id}")

        logger.info("Migration complete")


async def _seed_builtin_skills():
    from app.database import async_session_factory
    from app.models.skill import InstalledSkill
    from sqlalchemy import select

    async with async_session_factory() as db:
        result = await db.execute(select(InstalledSkill).where(InstalledSkill.name == "file_ops"))
        if not result.scalar_one_or_none():
            import json
            skill = InstalledSkill(
                name="file_ops",
                version="1.0.0",
                type="builtin",
                description="파일 시스템 도구 — 파일/디렉토리 생성, 읽기, 수정, 삭제",
                status="enabled",
                manifest=json.dumps({
                    "tools": ["file_create", "file_read", "file_write", "file_delete", "dir_list", "dir_create"],
                }),
            )
            db.add(skill)
            await db.commit()


async def _seed_sandbox_node():
    """Seed default SandboxNode if none exists."""
    from app.database import async_session_factory
    from app.models.sandbox_node import SandboxNode
    from sqlalchemy import select

    async with async_session_factory() as db:
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
            logger.info(f"Seeded default sandbox node: {settings.sandbox_default_node_host}")


async def _reconcile_containers():
    """Reconcile DB state with actual Docker containers on startup."""
    from app.database import async_session_factory
    from app.services.container_manager import ContainerManager

    try:
        async with async_session_factory() as db:
            cm = ContainerManager(db)
            await cm.reconcile()
    except Exception as e:
        logger.warning(f"Container reconciliation failed (Docker may not be available): {e}")


async def _stop_all_containers():
    """Stop all managed containers on shutdown."""
    from app.database import async_session_factory
    from app.services.container_manager import ContainerManager

    try:
        async with async_session_factory() as db:
            cm = ContainerManager(db)
            await cm.stop_all()
    except Exception as e:
        logger.warning(f"Failed to stop containers on shutdown: {e}")


app = FastAPI(title="haro", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(chats.router)
app.include_router(sessions.router)
app.include_router(messages.router)
app.include_router(files.router)
app.include_router(skills.router)
app.include_router(logs.router)
app.include_router(preview.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve frontend static files (built with `npm run build`)
import pathlib
_frontend_dist = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # Serve static assets (JS, CSS, etc.)
    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="static-assets")

    # Catch-all: serve index.html for SPA routing
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # If file exists in dist, serve it
        file_path = _frontend_dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html (SPA client-side routing)
        return FileResponse(str(_frontend_dist / "index.html"))
