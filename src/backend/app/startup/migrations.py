from __future__ import annotations

import logging

from sqlalchemy import text

import app.database as db_module

logger = logging.getLogger(__name__)


async def migrate_session_columns() -> None:
    """Add sandbox columns to sessions table if they don't exist (SQLite migration)."""
    async with db_module.engine.begin() as conn:
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
                    logger.info("Added column %s to sessions table", col_name)
                except Exception as exc:
                    logger.warning("Could not add column %s: %s", col_name, exc)


async def migrate_project_columns() -> None:
    """Add project columns introduced after the initial schema was created."""
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
                    logger.info("Added column %s to projects table", col_name)
                except Exception as exc:
                    logger.warning("Could not add project column %s: %s", col_name, exc)


async def migrate_chat_session_columns() -> None:
    """Add chat session columns introduced after the initial schema was created."""
    async with db_module.engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(chat_sessions)"))
        existing_cols = {row[1] for row in result.fetchall()}

        migrations = [
            ("folder_path", "ALTER TABLE chat_sessions ADD COLUMN folder_path VARCHAR(500)"),
        ]
        for col_name, sql in migrations:
            if col_name not in existing_cols:
                try:
                    await conn.execute(text(sql))
                    logger.info("Added column %s to chat_sessions table", col_name)
                except Exception as exc:
                    logger.warning("Could not add chat_session column %s: %s", col_name, exc)


async def migrate_sessions_to_projects() -> None:
    """Migrate existing sessions data to projects + chat_sessions tables."""
    async with db_module.engine.begin() as conn:
        await _rebuild_messages_table_if_needed(conn)
        await _rebuild_agent_logs_table_if_needed(conn)

        try:
            result = await conn.execute(text("SELECT COUNT(*) FROM sessions"))
            session_count = result.scalar()
        except Exception:
            session_count = 0

        if session_count == 0:
            logger.info("No sessions to migrate")
            return

        try:
            result = await conn.execute(text("SELECT COUNT(*) FROM projects"))
            project_count = result.scalar()
            if project_count > 0:
                logger.info("Projects table already has data, skipping migration")
                return
        except Exception:
            pass

        logger.info("Migrating %s sessions to projects + chat_sessions...", session_count)
        result = await conn.execute(text("SELECT * FROM sessions"))
        sessions = result.fetchall()
        columns = result.keys()

        for row in sessions:
            await _migrate_session_row(conn, dict(zip(columns, row)))

        logger.info("Migration complete")


async def _rebuild_messages_table_if_needed(conn) -> None:
    result = await conn.execute(text("PRAGMA table_info(messages)"))
    msg_cols = {row[1]: row for row in result.fetchall()}

    needs_rebuild = "chat_session_id" not in msg_cols
    if "session_id" in msg_cols and msg_cols["session_id"][3] == 1:
        needs_rebuild = True

    if not needs_rebuild:
        return

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
    except Exception as exc:
        logger.warning("Could not rebuild messages table: %s", exc)


async def _rebuild_agent_logs_table_if_needed(conn) -> None:
    result = await conn.execute(text("PRAGMA table_info(agent_logs)"))
    log_cols = {row[1]: row for row in result.fetchall()}

    needs_rebuild = "chat_session_id" not in log_cols
    if "session_id" in log_cols and log_cols["session_id"][3] == 1:
        needs_rebuild = True

    if not needs_rebuild:
        return

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
    except Exception as exc:
        logger.warning("Could not rebuild agent_logs table: %s", exc)


async def _migrate_session_row(conn, row_dict: dict) -> None:
    import uuid
    from datetime import datetime, timezone

    session_id = row_dict["id"]
    chat_session_id = str(uuid.uuid4())

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

    now = datetime.now(timezone.utc).isoformat()
    await conn.execute(text(
        "INSERT INTO chat_sessions (id, project_id, title, folder_path, created_at, updated_at) "
        "VALUES (:id, :project_id, :title, :folder_path, :created_at, :updated_at)"
    ), {
        "id": chat_session_id,
        "project_id": session_id,
        "title": "기본 채팅",
        "folder_path": None,
        "created_at": now,
        "updated_at": now,
    })

    await conn.execute(text(
        "UPDATE messages SET chat_session_id = :chat_session_id WHERE session_id = :session_id"
    ), {"chat_session_id": chat_session_id, "session_id": session_id})

    await conn.execute(text(
        "UPDATE agent_logs SET chat_session_id = :chat_session_id WHERE session_id = :session_id"
    ), {"chat_session_id": chat_session_id, "session_id": session_id})

    logger.info("Migrated session %s -> project + chat_session %s", session_id, chat_session_id)
