from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from app.services.harness import normalize_workspace_path
from app.services.workspace_file_connection import connect
from app.services.workspace_file_helpers import (
    db_path,
    escape_like,
    fts_phrase,
    make_snippet,
)
from app.services.workspace_file_lifecycle import ensure_workspace_file_db
from app.services.workspace_file_schema import ensure_schema, get_meta, read_count
from app.services.workspace_visibility_policy import (
    hidden_path_sql_condition,
    user_visible_sql_condition,
)


class WorkspaceSearchUnavailable(Exception):
    pass


def read_workspace_briefing_counts(workspace: str, chat_path: str | None = None) -> dict | None:
    """Read small count stats without creating, migrating, or rescanning the workspace DB."""
    path = db_path(workspace)
    if not os.path.isfile(path):
        return None

    try:
        uri = Path(path).resolve().as_uri() + "?mode=ro"
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
            "total_dirs": read_count(conn, "item_type = 'dir'"),
            "total_files": read_count(conn, "item_type = 'file'"),
            "root_dirs": read_count(conn, "parent_path = '/' AND item_type = 'dir'"),
        }

        if chat_path:
            normalized_chat_path = normalize_workspace_path(chat_path)
            prefix = f"{normalized_chat_path.rstrip('/')}/%"
            counts["chat_dirs"] = read_count(conn, "item_type = 'dir' AND path LIKE ?", (prefix,))
            counts["chat_files"] = read_count(conn, "item_type = 'file' AND path LIKE ?", (prefix,))

        has_meta = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'workspace_db_meta'"
        ).fetchone()
        if has_meta:
            counts["last_full_scan_at"] = get_meta(conn, "last_full_scan_at")
            counts["needs_rescan"] = get_meta(conn, "needs_rescan")

        return counts
    except Exception:
        return None
    finally:
        conn.close()


def list_workspace_directory_page(
    workspace: str,
    requested_path: str,
    *,
    limit: int | None = None,
    offset: int = 0,
    include_hidden: bool = True,
    user_id: str | None = None,
) -> dict:
    ensure_workspace_file_db(workspace)
    parent_path = normalize_workspace_path(requested_path)
    visibility_clause, visibility_params = _build_directory_visibility_filter(
        include_hidden=include_hidden,
        user_id=user_id,
    )
    conn = connect(workspace)
    try:
        total_row = conn.execute(
            f"""
            SELECT count(*)
            FROM workspace_items
            WHERE parent_path = ? AND path != '/' AND is_deleted = 0
              {visibility_clause}
            """,
            [parent_path, *visibility_params],
        ).fetchone()
        total = int(total_row[0] if total_row else 0)

        pagination = ""
        params: list[str | int] = [parent_path, *visibility_params]
        if limit is not None:
            pagination = "LIMIT ? OFFSET ?"
            params.extend([limit, max(offset, 0)])

        rows = conn.execute(
            f"""
            SELECT path, name, item_type, size_bytes
            FROM workspace_items
            WHERE parent_path = ? AND path != '/' AND is_deleted = 0
              {visibility_clause}
            ORDER BY item_type = 'file', lower(name)
            {pagination}
            """,
            params,
        ).fetchall()

        directory_paths = [row["path"] for row in rows if row["item_type"] == "dir"]
        children_counts: dict[str, int] = {}
        if directory_paths:
            placeholders = ",".join("?" for _ in directory_paths)
            count_rows = conn.execute(
                f"""
                SELECT parent_path, count(*) AS child_count
                FROM workspace_items
                WHERE parent_path IN ({placeholders}) AND path != '/' AND is_deleted = 0
                  {visibility_clause}
                GROUP BY parent_path
                """,
                [*directory_paths, *visibility_params],
            ).fetchall()
            children_counts = {row["parent_path"]: int(row["child_count"]) for row in count_rows}

        items: list[dict] = []
        for row in rows:
            children_count = None
            if row["item_type"] == "dir":
                children_count = children_counts.get(row["path"], 0)
            items.append({
                "name": row["name"],
                "type": "directory" if row["item_type"] == "dir" else "file",
                "size": row["size_bytes"],
                "children_count": children_count,
            })
        loaded_until = min(total, max(offset, 0) + len(items))
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": max(offset, 0),
            "has_more": loaded_until < total,
        }
    finally:
        conn.close()


def list_workspace_directory(workspace: str, requested_path: str) -> list[dict]:
    return list_workspace_directory_page(workspace, requested_path)["items"]


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
    include_hidden: bool = True,
    user_id: str | None = None,
) -> list[dict]:
    ensure_workspace_file_db(workspace)
    normalized_query = " ".join((query or "").strip().split())
    if not normalized_query:
        return []

    conn = connect(workspace)
    try:
        ensure_schema(conn)
        if get_meta(conn, "search_available") != "true":
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
        visibility_clause, visibility_params = _build_search_visibility_filter(
            include_hidden=include_hidden,
            user_id=user_id,
        )
        rows: list[sqlite3.Row] = []
        if len(normalized_query) >= 3:
            match_query = fts_phrase(normalized_query)
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
                      {visibility_clause}
                    LIMIT ?
                    """,
                    [match_query, *params, *visibility_params, limit],
                ).fetchall()
            except sqlite3.Error:
                rows = []

        if not rows:
            like_query = f"%{escape_like(normalized_query)}%"
            rows = conn.execute(
                f"""
                SELECT *
                FROM workspace_items wi
                WHERE wi.is_deleted = 0
                  AND wi.path != '/'
                  AND (wi.name LIKE ? ESCAPE '\\' OR wi.path LIKE ? ESCAPE '\\')
                  {filters}
                  {visibility_clause}
                ORDER BY item_type = 'file', lower(name)
                LIMIT ?
                """,
                [like_query, like_query, *params, *visibility_params, limit],
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
            params.append(f"{escape_like(normalized.rstrip('/'))}/%")
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

    conn = connect(workspace)
    try:
        ensure_schema(conn)
        row = conn.execute(
            f"SELECT count(*) FROM workspace_items WHERE {' AND '.join(clauses)}",
            params,
        ).fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def _build_search_filters(**filters: str | None) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    for key, value in filters.items():
        if value:
            clauses.append(f"AND wi.{key} = ?" if key != "extension" else "AND wi.extension = ?")
            params.append(value)
    return ("\n".join(clauses), params)


def _build_directory_visibility_filter(*, include_hidden: bool, user_id: str | None) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    if not include_hidden:
        clauses.append(f"AND {hidden_path_sql_condition('path')}")
        if user_id:
            visible_clause, visible_params = user_visible_sql_condition(
                user_id,
                column="path",
                include_ancestors=True,
            )
            clauses.append(f"AND {visible_clause}")
            params.extend(visible_params)
    return ("\n".join(clauses), params)


def _build_search_visibility_filter(*, include_hidden: bool, user_id: str | None) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    if not include_hidden:
        clauses.append(f"AND {hidden_path_sql_condition('wi.path')}")
        if user_id:
            visible_clause, visible_params = user_visible_sql_condition(
                user_id,
                column="wi.path",
                include_ancestors=False,
            )
            clauses.append(f"AND {visible_clause}")
            params.extend(visible_params)
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
        "summary_snippet": make_snippet(summary, query),
    }
