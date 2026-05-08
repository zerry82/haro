from __future__ import annotations

import os
import uuid

from app.services.harness import normalize_workspace_path
from app.services.workspace_file_connection import connect, now, workspace_writer_lock
from app.services.workspace_file_helpers import (
    LEGACY_META_DIR,
    META_DIR,
    full_path,
    is_meta_path,
    workspace_path_from_full,
)
from app.services.workspace_file_indexer import (
    delete_fts,
    mark_missing,
    rebuild_index,
    record_event,
    sync_path_with_parents,
    upsert_item,
)
from app.services.workspace_file_schema import ensure_schema, get_meta


def ensure_workspace_file_db(workspace: str) -> None:
    with workspace_writer_lock(workspace):
        conn = connect(workspace)
        try:
            ensure_schema(conn)
            if get_meta(conn, "last_full_scan_at") is None or get_meta(conn, "needs_rescan") == "true":
                rebuild_index(conn, workspace)
        finally:
            conn.close()


def rebuild_workspace_file_db(workspace: str) -> None:
    with workspace_writer_lock(workspace):
        conn = connect(workspace)
        try:
            ensure_schema(conn)
            rebuild_index(conn, workspace)
        finally:
            conn.close()


def sync_workspace_path(workspace: str, requested_path: str, source_kind: str = "local", chat_id: str | None = None) -> None:
    normalized = normalize_workspace_path(requested_path)
    if is_meta_path(normalized):
        return
    with workspace_writer_lock(workspace):
        conn = connect(workspace)
        try:
            ensure_schema(conn)
            with conn:
                if normalized != "/":
                    sync_path_with_parents(conn, workspace, normalized, source_kind=source_kind, chat_id=chat_id)
        finally:
            conn.close()


def sync_workspace_subtree(workspace: str, requested_path: str, source_kind: str = "local", chat_id: str | None = None) -> None:
    normalized = normalize_workspace_path(requested_path)
    if is_meta_path(normalized):
        return
    with workspace_writer_lock(workspace):
        conn = connect(workspace)
        try:
            ensure_schema(conn)
            full = full_path(workspace, normalized)
            if not os.path.exists(full):
                mark_missing(conn, normalized)
                return
            with conn:
                if normalized != "/":
                    sync_path_with_parents(conn, workspace, normalized, source_kind=source_kind, chat_id=chat_id)
                if os.path.isdir(full):
                    for root, dirnames, filenames in os.walk(full):
                        relative_root = workspace_path_from_full(workspace, root)
                        dirnames[:] = [name for name in dirnames if name not in {META_DIR, LEGACY_META_DIR}]
                        if relative_root != normalized:
                            upsert_item(conn, workspace, relative_root, source_kind=source_kind, chat_id=chat_id)
                        for filename in filenames:
                            path = normalize_workspace_path(f"{relative_root.rstrip('/')}/{filename}")
                            if not is_meta_path(path):
                                upsert_item(conn, workspace, path, source_kind=source_kind, chat_id=chat_id)
        finally:
            conn.close()


def mark_workspace_path_deleted(workspace: str, requested_path: str, actor_type: str = "system", chat_id: str | None = None) -> None:
    normalized = normalize_workspace_path(requested_path)
    if is_meta_path(normalized):
        return
    with workspace_writer_lock(workspace):
        conn = connect(workspace)
        try:
            ensure_schema(conn)
            current_time = now()
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
                        (current_time, current_time, row["id"]),
                    )
                    delete_fts(conn, row["id"])
                    record_event(conn, "deleted", row["path"], item_id=row["id"], actor_type=actor_type, chat_id=chat_id)
        finally:
            conn.close()


def update_workspace_item_summary(workspace: str, requested_path: str, summary_text: str | None) -> None:
    normalized = normalize_workspace_path(requested_path)
    if is_meta_path(normalized):
        return
    with workspace_writer_lock(workspace):
        conn = connect(workspace)
        try:
            ensure_schema(conn)
            full = full_path(workspace, normalized)
            if not os.path.exists(full):
                return
            with conn:
                sync_path_with_parents(conn, workspace, normalized, source_kind="local", chat_id=None)
                item_id = upsert_item(
                    conn,
                    workspace,
                    normalized,
                    source_kind="local",
                    summary_text=summary_text or "",
                    summary_status="fresh" if summary_text else "none",
                )
                record_event(conn, "indexed", normalized, item_id=item_id, actor_type="system")
        finally:
            conn.close()


def mark_workspace_summary_stale(workspace: str, requested_path: str) -> None:
    normalized = normalize_workspace_path(requested_path)
    if is_meta_path(normalized):
        return
    with workspace_writer_lock(workspace):
        conn = connect(workspace)
        try:
            ensure_schema(conn)
            full = full_path(workspace, normalized)
            if not os.path.exists(full):
                return
            with conn:
                sync_path_with_parents(conn, workspace, normalized, source_kind="local", chat_id=None)
                item_id = upsert_item(
                    conn,
                    workspace,
                    normalized,
                    source_kind="local",
                    summary_text="",
                    summary_status="stale",
                )
                record_event(conn, "indexed", normalized, item_id=item_id, actor_type="system")
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
        conn = connect(workspace)
        try:
            ensure_schema(conn)
            with conn:
                from_item_id = None
                to_item_id = None
                from_normalized = normalize_workspace_path(from_path) if from_path else None
                to_normalized = normalize_workspace_path(to_path) if to_path else None
                if from_normalized and not is_meta_path(from_normalized) and os.path.exists(full_path(workspace, from_normalized)):
                    from_item_id = upsert_item(conn, workspace, from_normalized, source_kind="chat", chat_id=chat_id)
                if to_normalized and not is_meta_path(to_normalized) and os.path.exists(full_path(workspace, to_normalized)):
                    to_item_id = upsert_item(conn, workspace, to_normalized, source_kind="chat", chat_id=chat_id)
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
                        now(),
                        metadata_json,
                    ),
                )
        finally:
            conn.close()
