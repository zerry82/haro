from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone

from app.services.harness import normalize_workspace_path
from app.services.workspace_file_helpers import (
    LEGACY_META_DIR,
    META_DIR,
    classify_path,
    full_path,
    is_meta_path,
    language_for_extension,
    parent_path,
    workspace_path_from_full,
)
from app.services.workspace_file_schema import get_meta, set_meta


def rebuild_index(conn: sqlite3.Connection, workspace: str) -> None:
    now = _now()
    seen: set[str] = set()
    with conn:
        record_event(conn, "rescan_started", "/", actor_type="system")
        for root, dirnames, filenames in os.walk(workspace):
            relative_root = workspace_path_from_full(workspace, root)
            dirnames[:] = [name for name in dirnames if name not in {META_DIR, LEGACY_META_DIR}]
            if is_meta_path(relative_root):
                continue
            if relative_root != "/":
                seen.add(relative_root)
                upsert_item(conn, workspace, relative_root, source_kind="local")
            for filename in filenames:
                path = normalize_workspace_path(f"{relative_root.rstrip('/')}/{filename}")
                if is_meta_path(path):
                    continue
                seen.add(path)
                upsert_item(conn, workspace, path, source_kind="local")

        active_rows = conn.execute("SELECT id, path FROM workspace_items WHERE is_deleted = 0").fetchall()
        for row in active_rows:
            if row["path"] not in seen:
                conn.execute(
                    "UPDATE workspace_items SET sync_status = 'missing', updated_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                delete_fts(conn, row["id"])
        set_meta(conn, "last_full_scan_at", now)
        set_meta(conn, "needs_rescan", "false")
        record_event(conn, "rescan_completed", "/", actor_type="system")


def sync_path_with_parents(
    conn: sqlite3.Connection,
    workspace: str,
    normalized: str,
    *,
    source_kind: str,
    chat_id: str | None,
) -> None:
    full = full_path(workspace, normalized)
    if not os.path.exists(full):
        mark_missing(conn, normalized)
        return

    parents: list[str] = []
    current = normalize_workspace_path(os.path.dirname(normalized))
    while current and current != "/":
        if is_meta_path(current):
            break
        parents.append(current)
        current = normalize_workspace_path(os.path.dirname(current))
    for parent in reversed(parents):
        if os.path.exists(full_path(workspace, parent)):
            upsert_item(conn, workspace, parent, source_kind=source_kind, chat_id=chat_id)
    upsert_item(conn, workspace, normalized, source_kind=source_kind, chat_id=chat_id)


def upsert_item(
    conn: sqlite3.Connection,
    workspace: str,
    normalized: str,
    *,
    source_kind: str,
    chat_id: str | None = None,
    summary_text: str | None = None,
    summary_status: str | None = None,
) -> str:
    full = full_path(workspace, normalized)
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
    room, access_policy, owner_user_id = classify_path(normalized)

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
            parent_path(normalized),
            name,
            "dir" if is_dir else "file",
            extension or None,
            language_for_extension(extension),
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
    upsert_fts(conn, item_id, name, normalized, final_summary if final_summary_status == "fresh" else "")
    return item_id


def mark_missing(conn: sqlite3.Connection, normalized: str) -> None:
    row = conn.execute("SELECT id FROM workspace_items WHERE path = ? AND is_deleted = 0", (normalized,)).fetchone()
    if not row:
        return
    now = _now()
    conn.execute(
        "UPDATE workspace_items SET sync_status = 'missing', updated_at = ? WHERE id = ?",
        (now, row["id"]),
    )
    delete_fts(conn, row["id"])


def upsert_fts(conn: sqlite3.Connection, item_id: str, name: str, path: str, summary_text: str) -> None:
    if get_meta(conn, "search_available") != "true":
        return
    delete_fts(conn, item_id)
    conn.execute(
        "INSERT INTO workspace_items_fts (item_id, name, path, summary_text) VALUES (?, ?, ?, ?)",
        (item_id, name, path, summary_text or ""),
    )


def delete_fts(conn: sqlite3.Connection, item_id: str) -> None:
    if get_meta(conn, "search_available") != "true":
        return
    conn.execute("DELETE FROM workspace_items_fts WHERE item_id = ?", (item_id,))


def record_event(
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
