from __future__ import annotations

import contextlib
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.services.harness import normalize_workspace_path

META_DIR = ".haro"
LEGACY_META_DIR = ".openclaw"
SCHEMA_VERSION = "1"

_PROCESS_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


class WorkspaceSearchUnavailable(Exception):
    pass


def ensure_workspace_file_db(workspace: str) -> None:
    with workspace_writer_lock(workspace):
        conn = _connect(workspace)
        try:
            _ensure_schema(conn)
            if _get_meta(conn, "last_full_scan_at") is None or _get_meta(conn, "needs_rescan") == "true":
                _rebuild_index(conn, workspace)
        finally:
            conn.close()


def rebuild_workspace_file_db(workspace: str) -> None:
    with workspace_writer_lock(workspace):
        conn = _connect(workspace)
        try:
            _ensure_schema(conn)
            _rebuild_index(conn, workspace)
        finally:
            conn.close()


def read_workspace_briefing_counts(workspace: str, chat_path: str | None = None) -> dict | None:
    """Read small count stats without creating, migrating, or rescanning the workspace DB."""
    db_path = _db_path(workspace)
    if not os.path.isfile(db_path):
        return None

    try:
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=1)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=1000")
        conn.execute("PRAGMA query_only=TRUE")
    except Exception:
        return None

    try:
        has_items = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'virtual table') AND name = 'workspace_items'"
        ).fetchone()
        if not has_items:
            return None

        counts: dict[str, int | str | None] = {
            "total_dirs": _read_count(conn, "item_type = 'dir'"),
            "total_files": _read_count(conn, "item_type = 'file'"),
            "root_dirs": _read_count(conn, "parent_path = '/' AND item_type = 'dir'"),
        }

        if chat_path:
            normalized_chat_path = normalize_workspace_path(chat_path)
            prefix = f"{normalized_chat_path.rstrip('/')}/%"
            counts["chat_dirs"] = _read_count(conn, "item_type = 'dir' AND path LIKE ?", (prefix,))
            counts["chat_files"] = _read_count(conn, "item_type = 'file' AND path LIKE ?", (prefix,))

        has_meta = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'workspace_db_meta'"
        ).fetchone()
        if has_meta:
            counts["last_full_scan_at"] = _get_meta(conn, "last_full_scan_at")
            counts["needs_rescan"] = _get_meta(conn, "needs_rescan")

        return counts
    except Exception:
        return None
    finally:
        conn.close()


def list_workspace_directory(workspace: str, requested_path: str) -> list[dict]:
    ensure_workspace_file_db(workspace)
    parent_path = normalize_workspace_path(requested_path)
    conn = _connect(workspace)
    try:
        rows = conn.execute(
            """
            SELECT path, name, item_type, size_bytes
            FROM workspace_items
            WHERE parent_path = ? AND path != '/' AND is_deleted = 0
            ORDER BY item_type = 'file', lower(name)
            """,
            (parent_path,),
        ).fetchall()
        items: list[dict] = []
        for row in rows:
            children_count = None
            if row["item_type"] == "dir":
                children_count = conn.execute(
                    "SELECT count(*) FROM workspace_items WHERE parent_path = ? AND path != '/' AND is_deleted = 0",
                    (row["path"],),
                ).fetchone()[0]
            items.append({
                "name": row["name"],
                "type": "directory" if row["item_type"] == "dir" else "file",
                "size": row["size_bytes"],
                "children_count": children_count,
            })
        return items
    finally:
        conn.close()


def sync_workspace_path(workspace: str, requested_path: str, source_kind: str = "local", chat_id: str | None = None) -> None:
    normalized = normalize_workspace_path(requested_path)
    if _is_meta_path(normalized):
        return
    with workspace_writer_lock(workspace):
        conn = _connect(workspace)
        try:
            _ensure_schema(conn)
            with conn:
                if normalized != "/":
                    _sync_path_with_parents(conn, workspace, normalized, source_kind=source_kind, chat_id=chat_id)
        finally:
            conn.close()


def sync_workspace_subtree(workspace: str, requested_path: str, source_kind: str = "local", chat_id: str | None = None) -> None:
    normalized = normalize_workspace_path(requested_path)
    if _is_meta_path(normalized):
        return
    with workspace_writer_lock(workspace):
        conn = _connect(workspace)
        try:
            _ensure_schema(conn)
            full = _full_path(workspace, normalized)
            if not os.path.exists(full):
                _mark_missing(conn, normalized)
                return
            with conn:
                if normalized != "/":
                    _sync_path_with_parents(conn, workspace, normalized, source_kind=source_kind, chat_id=chat_id)
                if os.path.isdir(full):
                    for root, dirnames, filenames in os.walk(full):
                        relative_root = _workspace_path_from_full(workspace, root)
                        dirnames[:] = [name for name in dirnames if name not in {META_DIR, LEGACY_META_DIR}]
                        if relative_root != normalized:
                            _upsert_item(conn, workspace, relative_root, source_kind=source_kind, chat_id=chat_id)
                        for filename in filenames:
                            path = normalize_workspace_path(f"{relative_root.rstrip('/')}/{filename}")
                            if not _is_meta_path(path):
                                _upsert_item(conn, workspace, path, source_kind=source_kind, chat_id=chat_id)
        finally:
            conn.close()


def mark_workspace_path_deleted(workspace: str, requested_path: str, actor_type: str = "system", chat_id: str | None = None) -> None:
    normalized = normalize_workspace_path(requested_path)
    if _is_meta_path(normalized):
        return
    with workspace_writer_lock(workspace):
        conn = _connect(workspace)
        try:
            _ensure_schema(conn)
            now = _now()
            with conn:
                rows = conn.execute(
                    "SELECT id, path FROM workspace_items WHERE (path = ? OR path LIKE ?) AND is_deleted = 0",
                    (normalized, f"{normalized.rstrip('/')}/%"),
                ).fetchall()
                for row in rows:
                    conn.execute(
                        """
                        UPDATE workspace_items
                        SET is_deleted = 1, deleted_at = ?, updated_at = ?, sync_status = 'synced'
                        WHERE id = ?
                        """,
                        (now, now, row["id"]),
                    )
                    _delete_fts(conn, row["id"])
                    _record_event(conn, "deleted", row["path"], item_id=row["id"], actor_type=actor_type, chat_id=chat_id)
        finally:
            conn.close()


def update_workspace_item_summary(workspace: str, requested_path: str, summary_text: str | None) -> None:
    normalized = normalize_workspace_path(requested_path)
    if _is_meta_path(normalized):
        return
    with workspace_writer_lock(workspace):
        conn = _connect(workspace)
        try:
            _ensure_schema(conn)
            full = _full_path(workspace, normalized)
            if not os.path.exists(full):
                return
            with conn:
                item_id = _upsert_item(
                    conn,
                    workspace,
                    normalized,
                    source_kind="local",
                    summary_text=summary_text or "",
                    summary_status="fresh" if summary_text else "none",
                )
                _record_event(conn, "indexed", normalized, item_id=item_id, actor_type="system")
        finally:
            conn.close()


def mark_workspace_summary_stale(workspace: str, requested_path: str) -> None:
    normalized = normalize_workspace_path(requested_path)
    if _is_meta_path(normalized):
        return
    with workspace_writer_lock(workspace):
        conn = _connect(workspace)
        try:
            _ensure_schema(conn)
            full = _full_path(workspace, normalized)
            if not os.path.exists(full):
                return
            with conn:
                item_id = _upsert_item(
                    conn,
                    workspace,
                    normalized,
                    source_kind="local",
                    summary_text="",
                    summary_status="stale",
                )
                _record_event(conn, "indexed", normalized, item_id=item_id, actor_type="system")
        finally:
            conn.close()


def record_workspace_relation(
    workspace: str,
    relation_type: str,
    *,
    from_path: str | None = None,
    to_path: str | None = None,
    chat_id: str | None = None,
    actor_id: str | None = None,
    metadata_json: str | None = None,
) -> None:
    with workspace_writer_lock(workspace):
        conn = _connect(workspace)
        try:
            _ensure_schema(conn)
            with conn:
                from_item_id = None
                to_item_id = None
                from_normalized = normalize_workspace_path(from_path) if from_path else None
                to_normalized = normalize_workspace_path(to_path) if to_path else None
                if from_normalized and not _is_meta_path(from_normalized) and os.path.exists(_full_path(workspace, from_normalized)):
                    from_item_id = _upsert_item(conn, workspace, from_normalized, source_kind="chat", chat_id=chat_id)
                if to_normalized and not _is_meta_path(to_normalized) and os.path.exists(_full_path(workspace, to_normalized)):
                    to_item_id = _upsert_item(conn, workspace, to_normalized, source_kind="chat", chat_id=chat_id)
                conn.execute(
                    """
                    INSERT INTO workspace_item_relations
                    (id, from_item_id, from_path, to_item_id, to_path, relation_type, chat_id, created_by_user_id, created_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        from_item_id,
                        from_normalized,
                        to_item_id,
                        to_normalized,
                        relation_type,
                        chat_id,
                        actor_id,
                        _now(),
                        metadata_json,
                    ),
                )
        finally:
            conn.close()


def search_workspace_files(
    workspace: str,
    query: str,
    *,
    room: str | None = None,
    item_type: str | None = None,
    language: str | None = None,
    extension: str | None = None,
    access_policy: str | None = None,
    chat_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    ensure_workspace_file_db(workspace)
    normalized_query = " ".join((query or "").strip().split())
    if not normalized_query:
        return []

    conn = _connect(workspace)
    try:
        _ensure_schema(conn)
        if _get_meta(conn, "search_available") != "true":
            raise WorkspaceSearchUnavailable("workspace file search is unavailable")

        item_type = _normalize_item_type_filter(item_type)
        filters, params = _build_search_filters(
            room=room,
            item_type=item_type,
            language=language,
            extension=extension,
            access_policy=access_policy,
            chat_id=chat_id,
        )
        rows: list[sqlite3.Row] = []
        if len(normalized_query) >= 3:
            match_query = _fts_phrase(normalized_query)
            try:
                rows = conn.execute(
                    f"""
                    SELECT wi.*
                    FROM workspace_items_fts
                    JOIN workspace_items wi ON wi.id = workspace_items_fts.item_id
                    WHERE workspace_items_fts MATCH ?
                      AND wi.is_deleted = 0
                      AND wi.path != '/'
                      {filters}
                    LIMIT ?
                    """,
                    [match_query, *params, limit],
                ).fetchall()
            except sqlite3.Error:
                rows = []

        if not rows:
            like_query = f"%{_escape_like(normalized_query)}%"
            rows = conn.execute(
                f"""
                SELECT *
                FROM workspace_items wi
                WHERE wi.is_deleted = 0
                  AND wi.path != '/'
                  AND (wi.name LIKE ? ESCAPE '\\' OR wi.path LIKE ? ESCAPE '\\')
                  {filters}
                ORDER BY item_type = 'file', lower(name)
                LIMIT ?
                """,
                [like_query, like_query, *params, limit],
            ).fetchall()

        return [_search_row_to_dict(row, normalized_query) for row in rows]
    finally:
        conn.close()


def count_workspace_items(
    workspace: str,
    requested_path: str = "/",
    *,
    item_type: str | None = None,
    recursive: bool = False,
    room: str | None = None,
    access_policy: str | None = None,
    chat_id: str | None = None,
) -> int:
    ensure_workspace_file_db(workspace)
    normalized = normalize_workspace_path(requested_path)
    db_item_type = _normalize_item_type_filter(item_type)

    clauses = ["is_deleted = 0", "path != '/'"]
    params: list[str] = []
    if recursive:
        if normalized != "/":
            clauses.append("path LIKE ? ESCAPE '\\'")
            params.append(f"{_escape_like(normalized.rstrip('/'))}/%")
    else:
        clauses.append("parent_path = ?")
        params.append(normalized)
    if db_item_type:
        clauses.append("item_type = ?")
        params.append(db_item_type)
    if room:
        clauses.append("room = ?")
        params.append(room)
    if access_policy:
        clauses.append("access_policy = ?")
        params.append(access_policy)
    if chat_id:
        clauses.append("chat_id = ?")
        params.append(chat_id)

    conn = _connect(workspace)
    try:
        _ensure_schema(conn)
        row = conn.execute(
            f"SELECT count(*) FROM workspace_items WHERE {' AND '.join(clauses)}",
            params,
        ).fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def atomic_write_text(path: str, content: str) -> None:
    _atomic_write_bytes(path, content.encode("utf-8"))


def atomic_write_bytes(path: str, content: bytes) -> None:
    _atomic_write_bytes(path, content)


@contextlib.contextmanager
def workspace_writer_lock(workspace: str) -> Iterator[None]:
    workspace_real = os.path.realpath(workspace)
    process_lock = _get_process_lock(workspace_real)
    with process_lock:
        os.makedirs(os.path.join(workspace_real, META_DIR, "locks"), exist_ok=True)
        lock_path = os.path.join(workspace_real, META_DIR, "locks", "workspace-db.lock")
        with open(lock_path, "a+b") as lock_file:
            _lock_file(lock_file)
            try:
                yield
            finally:
                _unlock_file(lock_file)


def _connect(workspace: str) -> sqlite3.Connection:
    db_path = _db_path(workspace)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=DELETE")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
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
        _set_meta(conn, "schema_version", SCHEMA_VERSION)

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
            _set_meta(conn, "search_available", "true")
    except sqlite3.Error:
        with conn:
            _set_meta(conn, "search_available", "false")


def _rebuild_index(conn: sqlite3.Connection, workspace: str) -> None:
    now = _now()
    seen: set[str] = set()
    with conn:
        _record_event(conn, "rescan_started", "/", actor_type="system")
        for root, dirnames, filenames in os.walk(workspace):
            relative_root = _workspace_path_from_full(workspace, root)
            dirnames[:] = [name for name in dirnames if name not in {META_DIR, LEGACY_META_DIR}]
            if _is_meta_path(relative_root):
                continue
            if relative_root != "/":
                seen.add(relative_root)
                _upsert_item(conn, workspace, relative_root, source_kind="local")
            for filename in filenames:
                path = normalize_workspace_path(f"{relative_root.rstrip('/')}/{filename}")
                if _is_meta_path(path):
                    continue
                seen.add(path)
                _upsert_item(conn, workspace, path, source_kind="local")

        active_rows = conn.execute("SELECT id, path FROM workspace_items WHERE is_deleted = 0").fetchall()
        for row in active_rows:
            if row["path"] not in seen:
                conn.execute(
                    "UPDATE workspace_items SET sync_status = 'missing', updated_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                _delete_fts(conn, row["id"])
        _set_meta(conn, "last_full_scan_at", now)
        _set_meta(conn, "needs_rescan", "false")
        _record_event(conn, "rescan_completed", "/", actor_type="system")


def _sync_path_with_parents(
    conn: sqlite3.Connection,
    workspace: str,
    normalized: str,
    *,
    source_kind: str,
    chat_id: str | None,
) -> None:
    full = _full_path(workspace, normalized)
    if not os.path.exists(full):
        _mark_missing(conn, normalized)
        return

    parents: list[str] = []
    current = normalize_workspace_path(os.path.dirname(normalized))
    while current and current != "/":
        if _is_meta_path(current):
            break
        parents.append(current)
        current = normalize_workspace_path(os.path.dirname(current))
    for parent in reversed(parents):
        if os.path.exists(_full_path(workspace, parent)):
            _upsert_item(conn, workspace, parent, source_kind=source_kind, chat_id=chat_id)
    _upsert_item(conn, workspace, normalized, source_kind=source_kind, chat_id=chat_id)


def _upsert_item(
    conn: sqlite3.Connection,
    workspace: str,
    normalized: str,
    *,
    source_kind: str,
    chat_id: str | None = None,
    summary_text: str | None = None,
    summary_status: str | None = None,
) -> str:
    full = _full_path(workspace, normalized)
    stat = os.stat(full)
    is_dir = os.path.isdir(full)
    now = _now()
    existing = conn.execute(
        "SELECT id, created_at FROM workspace_items WHERE path = ? AND is_deleted = 0",
        (normalized,),
    ).fetchone()
    item_id = existing["id"] if existing else str(uuid.uuid4())
    created_at = existing["created_at"] if existing else now
    name = os.path.basename(normalized.rstrip("/")) or "/"
    extension = "" if is_dir else os.path.splitext(name)[1].lower()
    inferred_summary, inferred_status = _read_summary(workspace, normalized) if not is_dir else ("", "none")
    final_summary = summary_text if summary_text is not None else inferred_summary
    final_summary_status = summary_status or inferred_status
    room, access_policy, owner_user_id = _classify_path(normalized)

    conn.execute(
        """
        INSERT INTO workspace_items (
            id, path, parent_path, name, item_type, extension, language, mime_type,
            size_bytes, mtime_ms, content_hash, summary_text, summary_status, summary_updated_at,
            room, access_policy, owner_user_id, chat_id, source_kind, sync_status, is_deleted,
            last_seen_at, indexed_at, created_at, updated_at, deleted_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced', 0, ?, ?, ?, ?, NULL, NULL)
        ON CONFLICT(id) DO UPDATE SET
            parent_path = excluded.parent_path,
            name = excluded.name,
            item_type = excluded.item_type,
            extension = excluded.extension,
            language = excluded.language,
            mime_type = excluded.mime_type,
            size_bytes = excluded.size_bytes,
            mtime_ms = excluded.mtime_ms,
            summary_text = excluded.summary_text,
            summary_status = excluded.summary_status,
            summary_updated_at = excluded.summary_updated_at,
            room = excluded.room,
            access_policy = excluded.access_policy,
            owner_user_id = excluded.owner_user_id,
            chat_id = COALESCE(excluded.chat_id, workspace_items.chat_id),
            source_kind = excluded.source_kind,
            sync_status = 'synced',
            is_deleted = 0,
            last_seen_at = excluded.last_seen_at,
            indexed_at = excluded.indexed_at,
            updated_at = excluded.updated_at,
            deleted_at = NULL
        """,
        (
            item_id,
            normalized,
            _parent_path(normalized),
            name,
            "dir" if is_dir else "file",
            extension or None,
            _language_for_extension(extension),
            None,
            None if is_dir else stat.st_size,
            int(stat.st_mtime * 1000),
            None,
            final_summary,
            final_summary_status,
            now if final_summary_status == "fresh" else None,
            room,
            access_policy,
            owner_user_id,
            chat_id,
            source_kind,
            now,
            now,
            created_at,
            now,
        ),
    )
    _upsert_fts(conn, item_id, name, normalized, final_summary if final_summary_status == "fresh" else "")
    return item_id


def _mark_missing(conn: sqlite3.Connection, normalized: str) -> None:
    row = conn.execute("SELECT id FROM workspace_items WHERE path = ? AND is_deleted = 0", (normalized,)).fetchone()
    if not row:
        return
    now = _now()
    conn.execute(
        "UPDATE workspace_items SET sync_status = 'missing', updated_at = ? WHERE id = ?",
        (now, row["id"]),
    )
    _delete_fts(conn, row["id"])


def _upsert_fts(conn: sqlite3.Connection, item_id: str, name: str, path: str, summary_text: str) -> None:
    if _get_meta(conn, "search_available") != "true":
        return
    _delete_fts(conn, item_id)
    conn.execute(
        "INSERT INTO workspace_items_fts (item_id, name, path, summary_text) VALUES (?, ?, ?, ?)",
        (item_id, name, path, summary_text or ""),
    )


def _delete_fts(conn: sqlite3.Connection, item_id: str) -> None:
    if _get_meta(conn, "search_available") != "true":
        return
    conn.execute("DELETE FROM workspace_items_fts WHERE item_id = ?", (item_id,))


def _record_event(
    conn: sqlite3.Connection,
    event_type: str,
    path: str,
    *,
    item_id: str | None = None,
    old_path: str | None = None,
    actor_type: str = "system",
    actor_id: str | None = None,
    chat_id: str | None = None,
    metadata_json: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO workspace_file_events
        (event_type, item_id, path, old_path, actor_type, actor_id, chat_id, created_at, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_type, item_id, path, old_path, actor_type, actor_id, chat_id, _now(), metadata_json),
    )


def _build_search_filters(**filters: str | None) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    for key, value in filters.items():
        if value:
            clauses.append(f"AND wi.{key} = ?" if key != "extension" else "AND wi.extension = ?")
            params.append(value)
    return ("\n".join(clauses), params)


def _normalize_item_type_filter(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if lowered in {"dir", "directory", "folder", "folders"}:
        return "dir"
    if lowered in {"file", "files"}:
        return "file"
    return lowered


def _search_row_to_dict(row: sqlite3.Row, query: str) -> dict:
    summary = row["summary_text"] or ""
    return {
        "path": row["path"],
        "name": row["name"],
        "item_type": "directory" if row["item_type"] == "dir" else "file",
        "language": row["language"] or "plaintext",
        "extension": row["extension"],
        "room": row["room"],
        "access_policy": row["access_policy"],
        "summary_status": row["summary_status"],
        "summary_snippet": _make_snippet(summary, query),
    }


def _make_snippet(summary: str, query: str) -> str:
    text = " ".join(summary.split())
    if not text:
        return ""
    lowered = text.lower()
    index = lowered.find(query.lower())
    if index < 0:
        return text[:160]
    start = max(0, index - 50)
    end = min(len(text), index + len(query) + 80)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _classify_path(path: str) -> tuple[str, str, str | None]:
    parts = [part for part in path.strip("/").split("/") if part]
    if not parts:
        return "root", "writable", None
    if parts[0] == "clean-room":
        if len(parts) > 1 and parts[1] == "data":
            return "clean_room_data", "read_only", None
        return "clean_room_meta", "read_only", None
    if parts[0] == "playground":
        owner_user_id = parts[2] if len(parts) >= 3 and parts[1] == "users" else None
        return "playground", "writable", owner_user_id
    if parts[0] == "90_archive":
        return "archive", "read_only", None
    return "root", "writable", None


def _read_summary(workspace: str, path: str) -> tuple[str, str]:
    summary_name = path.strip("/").replace("/", "__").replace("\\", "__") + ".md"
    summary_path = os.path.join(workspace, META_DIR, "file_summaries", summary_name)
    if not os.path.isfile(summary_path):
        return "", "none"
    try:
        with open(summary_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip(), "fresh"
    except Exception:
        return "", "error"


def _language_for_extension(extension: str) -> str | None:
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".csv": "csv",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".txt": "plaintext",
        ".svg": "xml",
    }.get(extension)


def _fts_phrase(query: str) -> str:
    return f'"{query.replace(chr(34), chr(34) + chr(34))}"'


def _escape_like(query: str) -> str:
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parent_path(path: str) -> str:
    parent = normalize_workspace_path(os.path.dirname(path.rstrip("/")))
    return parent if parent != "/." else "/"


def _workspace_path_from_full(workspace: str, full_path: str) -> str:
    rel = os.path.relpath(full_path, workspace).replace("\\", "/")
    if rel == ".":
        return "/"
    return normalize_workspace_path(rel)


def _full_path(workspace: str, requested: str) -> str:
    normalized = normalize_workspace_path(requested)
    workspace_real = os.path.realpath(workspace)
    full = os.path.realpath(os.path.join(workspace_real, normalized.lstrip("/")))
    if os.path.commonpath([workspace_real, full]) != workspace_real:
        raise PermissionError("워크스페이스 외부 접근 불가")
    return full


def _db_path(workspace: str) -> str:
    return os.path.join(workspace, META_DIR, "db", "workspace.db")


def _is_meta_path(path: str) -> bool:
    normalized = normalize_workspace_path(path)
    return any(normalized == f"/{name}" or normalized.startswith(f"/{name}/") for name in (META_DIR, LEGACY_META_DIR))


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM workspace_db_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _read_count(conn: sqlite3.Connection, where_clause: str, params: tuple = ()) -> int:
    row = conn.execute(
        f"SELECT count(*) FROM workspace_items WHERE is_deleted = 0 AND path != '/' AND {where_clause}",
        params,
    ).fetchone()
    return int(row[0] if row else 0)


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO workspace_db_meta (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, _now()),
    )


def _atomic_write_bytes(path: str, content: bytes) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temp_path = os.path.join(directory, f".{os.path.basename(path)}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temp_path, "wb") as f:
            f.write(content)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            with contextlib.suppress(OSError):
                os.remove(temp_path)


def _get_process_lock(workspace: str) -> threading.RLock:
    with _PROCESS_LOCKS_GUARD:
        lock = _PROCESS_LOCKS.get(workspace)
        if lock is None:
            lock = threading.RLock()
            _PROCESS_LOCKS[workspace] = lock
        return lock


def _lock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _unlock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt
        lock_file.seek(0)
        with contextlib.suppress(OSError):
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
