from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path
from typing import Any

from app.services.workspace_file_db import atomic_write_text, sync_workspace_path

CONTEXT_DB_VERSION = "1"
META_DIR = ".haro"


class ContextLibrarySearchUnavailable(Exception):
    pass


def context_db_path(workspace: str) -> str:
    return os.path.join(workspace, META_DIR, "db", "context_library.db")


def ensure_context_library_db(workspace: str) -> str:
    path = context_db_path(workspace)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _connect(path) as conn:
        _ensure_schema(conn)
    return path


def search_context_library(workspace: str, query: str, limit: int = 20) -> dict[str, Any]:
    db_file = ensure_context_library_db(workspace)
    normalized_query = " ".join((query or "").split())
    if not normalized_query:
        return {"query": query, "status": "ok", "items": []}
    with _connect(db_file) as conn:
        if _get_meta(conn, "search_available") == "true":
            rows = _search_fts(conn, normalized_query, limit)
        else:
            rows = _search_like(conn, normalized_query, limit)
    return {"query": query, "status": "ok", "items": rows}


def promote_mail_threads(workspace: str, staging_threads: list[Any]) -> list[dict[str, Any]]:
    ensure_context_library_db(workspace)
    promoted: list[dict[str, Any]] = []
    for staging in staging_threads:
        if staging.inclusion_decision != "allowed":
            continue
        item = _context_item_from_staging(staging)
        clean_room_path = _write_summary_file(workspace, item)
        item["clean_room_path"] = clean_room_path
        _upsert_context_item(workspace, item)
        promoted.append({
            "staging_id": staging.id,
            "id": item["id"],
            "title": item["title"],
            "category": item["category"],
            "clean_room_path": clean_room_path,
        })
    return promoted


def _context_item_from_staging(staging: Any) -> dict[str, Any]:
    attachments = _loads(staging.attachments_json, [])
    recipients = _loads(staging.recipients_json, [])
    sender_domain = _sender_domain(staging.sender)
    source_hash = _stable_source_key(staging.source_ref)
    return {
        "id": f"ctx-{source_hash}",
        "title": staging.subject,
        "summary": staging.summary,
        "category": staging.category,
        "source_kind": "gmail_thread",
        "source_ref": source_hash,
        "received_at": staging.received_at,
        "properties": {
            "sender_domain": sender_domain,
            "recipient_count": len(recipients),
            "attachment_count": len(attachments),
            "attachments": [
                {
                    "title": attachment.get("title"),
                    "extension": attachment.get("extension"),
                    "size_bytes": attachment.get("size_bytes"),
                    "summary": attachment.get("summary") or "",
                }
                for attachment in attachments
            ],
        },
        "relations": _relations_for_thread(source_hash, staging.category, sender_domain, attachments),
    }


def _write_summary_file(workspace: str, item: dict[str, Any]) -> str:
    date_part = _date_folder(item.get("received_at"))
    slug = _slug(item["title"]) or item["id"]
    relative_path = f"/clean-room/data/10_sources/mail/{date_part}/{slug}.md"
    full_path = _full_path(workspace, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    atomic_write_text(full_path, _summary_markdown(item))
    sync_workspace_path(workspace, relative_path, source_kind="context_library")
    return relative_path


def _upsert_context_item(workspace: str, item: dict[str, Any]) -> None:
    db_file = ensure_context_library_db(workspace)
    now = _now()
    with _connect(db_file) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO context_items (
                    id, title, summary, category, source_kind, source_ref,
                    clean_room_path, properties_json, is_deleted, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    summary = excluded.summary,
                    category = excluded.category,
                    clean_room_path = excluded.clean_room_path,
                    properties_json = excluded.properties_json,
                    is_deleted = 0,
                    updated_at = excluded.updated_at
                """,
                (
                    item["id"],
                    item["title"],
                    item["summary"],
                    item["category"],
                    item["source_kind"],
                    item["source_ref"],
                    item["clean_room_path"],
                    json.dumps(item["properties"], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            _delete_fts(conn, item["id"])
            _upsert_fts(conn, item)
            conn.execute("DELETE FROM context_relations WHERE from_item_id = ?", (item["id"],))
            for relation in item.get("relations", []):
                conn.execute(
                    """
                    INSERT INTO context_relations (
                        id, from_item_id, relation_type, to_key, to_label, metadata_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        item["id"],
                        relation["relation_type"],
                        relation["to_key"],
                        relation["to_label"],
                        json.dumps(relation.get("metadata") or {}, ensure_ascii=False),
                        now,
                    ),
                )


def _ensure_schema(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS context_items (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                category TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                clean_room_path TEXT NOT NULL,
                properties_json TEXT NOT NULL,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_context_items_source ON context_items(source_kind, source_ref)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_context_items_category ON context_items(category, is_deleted)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS context_relations (
                id TEXT PRIMARY KEY,
                from_item_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                to_key TEXT NOT NULL,
                to_label TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_context_relations_from ON context_relations(from_item_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_context_relations_to ON context_relations(to_key)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS context_db_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        _set_meta(conn, "schema_version", CONTEXT_DB_VERSION)
    try:
        with conn:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS context_items_fts USING fts5(
                    item_id UNINDEXED,
                    title,
                    summary,
                    category,
                    tokenize='trigram'
                )
            """)
            _set_meta(conn, "search_available", "true")
    except sqlite3.Error:
        with conn:
            _set_meta(conn, "search_available", "false")


def _search_fts(conn: sqlite3.Connection, query: str, limit: int) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT ci.id, ci.title, ci.summary, ci.category, ci.clean_room_path, ci.properties_json
            FROM context_items_fts
            JOIN context_items ci ON ci.id = context_items_fts.item_id
            WHERE context_items_fts MATCH ? AND ci.is_deleted = 0
            ORDER BY rank
            LIMIT ?
            """,
            (_fts_phrase(query), limit),
        ).fetchall()
    except sqlite3.Error:
        return _search_like(conn, query, limit)
    return [_row_to_item(row) for row in rows]


def _search_like(conn: sqlite3.Connection, query: str, limit: int) -> list[dict[str, Any]]:
    pattern = f"%{query}%"
    rows = conn.execute(
        """
        SELECT id, title, summary, category, clean_room_path, properties_json
        FROM context_items
        WHERE is_deleted = 0 AND (title LIKE ? OR summary LIKE ? OR category LIKE ?)
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (pattern, pattern, pattern, limit),
    ).fetchall()
    return [_row_to_item(row) for row in rows]


def _upsert_fts(conn: sqlite3.Connection, item: dict[str, Any]) -> None:
    if _get_meta(conn, "search_available") != "true":
        return
    conn.execute(
        "INSERT INTO context_items_fts (item_id, title, summary, category) VALUES (?, ?, ?, ?)",
        (item["id"], item["title"], item["summary"], item["category"]),
    )


def _delete_fts(conn: sqlite3.Connection, item_id: str) -> None:
    if _get_meta(conn, "search_available") != "true":
        return
    conn.execute("DELETE FROM context_items_fts WHERE item_id = ?", (item_id,))


def _relations_for_thread(source_hash: str, category: str, sender_domain: str, attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relations = [
        {"relation_type": "categorized_as", "to_key": f"category:{category}", "to_label": category},
    ]
    if sender_domain:
        relations.append({"relation_type": "from_domain", "to_key": f"domain:{sender_domain}", "to_label": sender_domain})
    for attachment in attachments:
        title = str(attachment.get("title") or "").strip()
        if title:
            relations.append({
                "relation_type": "has_attachment",
                "to_key": f"attachment:{source_hash}:{_slug(title)}",
                "to_label": title,
                "metadata": {
                    "extension": attachment.get("extension"),
                    "size_bytes": attachment.get("size_bytes"),
                },
            })
    return relations


def _summary_markdown(item: dict[str, Any]) -> str:
    properties = item["properties"]
    attachment_lines = []
    for attachment in properties.get("attachments") or []:
        label = f"- {attachment.get('title')} ({attachment.get('extension') or 'file'}, {attachment.get('size_bytes') or 0} bytes)"
        if attachment.get("summary"):
            label = f"{label}: {attachment['summary']}"
        attachment_lines.append(label)
    if not attachment_lines:
        attachment_lines = ["- none"]
    return "\n".join([
        f"# {item['title']}",
        "",
        f"- Category: {item['category']}",
        f"- Source: {item['source_kind']}",
        f"- Sender domain: {properties.get('sender_domain') or 'unknown'}",
        "",
        "## Summary",
        "",
        item["summary"],
        "",
        "## Attachments",
        "",
        *attachment_lines,
        "",
    ])


def _row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "summary": row["summary"],
        "category": row["category"],
        "clean_room_path": row["clean_room_path"],
        "properties": _loads(row["properties_json"], {}),
    }


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM context_db_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO context_db_meta (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, _now()),
    )


def _full_path(workspace: str, relative_path: str) -> str:
    return str((Path(workspace) / relative_path.lstrip("/")).resolve())


def _date_folder(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).date().isoformat()
    return value[:10]


def _sender_domain(sender: str) -> str:
    address = parseaddr(sender)[1] or sender
    if "@" not in address:
        return ""
    return address.rsplit("@", 1)[1].casefold()


def _stable_source_key(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _slug(value: str) -> str:
    lowered = value.casefold()
    slug = re.sub(r"[^a-z0-9가-힣]+", "-", lowered).strip("-")
    return slug[:80]


def _fts_phrase(query: str) -> str:
    escaped = query.replace('"', '""')
    return f'"{escaped}"'


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
