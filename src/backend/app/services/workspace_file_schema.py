from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

SCHEMA_VERSION = "1"


def ensure_schema(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workspace_items (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                parent_path TEXT NOT NULL,
                name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                extension TEXT,
                language TEXT,
                mime_type TEXT,
                size_bytes INTEGER,
                mtime_ms INTEGER,
                content_hash TEXT,
                summary_text TEXT,
                summary_status TEXT NOT NULL DEFAULT 'none',
                summary_updated_at TEXT,
                room TEXT NOT NULL,
                access_policy TEXT NOT NULL,
                owner_user_id TEXT,
                chat_id TEXT,
                source_kind TEXT NOT NULL DEFAULT 'local',
                sync_status TEXT NOT NULL DEFAULT 'synced',
                is_deleted INTEGER NOT NULL DEFAULT 0,
                last_seen_at TEXT NOT NULL,
                indexed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT,
                metadata_json TEXT
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_items_active_path
            ON workspace_items(path)
            WHERE is_deleted = 0
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_items_parent ON workspace_items(parent_path, is_deleted)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_items_room ON workspace_items(room, is_deleted)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_items_access_policy ON workspace_items(access_policy, is_deleted)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_items_chat ON workspace_items(chat_id, is_deleted)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_items_sync ON workspace_items(sync_status, is_deleted)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workspace_item_relations (
                id TEXT PRIMARY KEY,
                from_item_id TEXT,
                from_path TEXT,
                to_item_id TEXT,
                to_path TEXT,
                relation_type TEXT NOT NULL,
                chat_id TEXT,
                created_by_user_id TEXT,
                created_at TEXT NOT NULL,
                metadata_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workspace_file_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                item_id TEXT,
                path TEXT NOT NULL,
                old_path TEXT,
                actor_type TEXT NOT NULL,
                actor_id TEXT,
                chat_id TEXT,
                created_at TEXT NOT NULL,
                metadata_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workspace_db_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        set_meta(conn, "schema_version", SCHEMA_VERSION)

    try:
        with conn:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS workspace_items_fts USING fts5(
                    item_id UNINDEXED,
                    name,
                    path,
                    summary_text,
                    tokenize='trigram'
                )
            """)
            set_meta(conn, "search_available", "true")
    except sqlite3.Error:
        with conn:
            set_meta(conn, "search_available", "false")


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM workspace_db_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def read_count(conn: sqlite3.Connection, where_clause: str, params: tuple = ()) -> int:
    row = conn.execute(
        f"SELECT count(*) FROM workspace_items WHERE is_deleted = 0 AND path != '/' AND {where_clause}",
        params,
    ).fetchone()
    return int(row[0] if row else 0)


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO workspace_db_meta (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, _now()),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
