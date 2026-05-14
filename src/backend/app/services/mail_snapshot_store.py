from __future__ import annotations

import json
import os
import re
import hashlib
from datetime import datetime, timezone
from typing import Any

from app.services.workspace_file_helpers import full_path

CACHE_PATH = "/.haro/cache/mail/gmail"
SNAPSHOT_VERSION = 1
SOURCE_REF_RE = re.compile(r"^gmail:[A-Za-z0-9_-]{1,128}$")


class MailSnapshotStoreError(ValueError):
    pass


class MailSnapshotStore:
    def __init__(self, workspace: str) -> None:
        self.workspace = os.path.realpath(workspace)
        self.cache_root = full_path(self.workspace, CACHE_PATH)

    def load_recent_threads(self, account_email: str, limit: int) -> list[dict[str, Any]]:
        index = self._read_index(account_email)
        rows = sorted(index.get("threads", []), key=lambda item: str(item.get("received_at") or ""), reverse=True)
        threads: list[dict[str, Any]] = []
        for row in rows[:_limit(limit)]:
            source_ref = str(row.get("source_ref") or "")
            thread = self.load_thread(account_email, source_ref)
            if thread:
                threads.append(thread)
        return threads

    def load_thread(self, account_email: str, source_ref: str) -> dict[str, Any] | None:
        path = self._thread_path(account_email, source_ref)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return None
        thread = data.get("thread")
        return thread if isinstance(thread, dict) else None

    def upsert_threads(self, account_email: str, threads: list[dict[str, Any]], fetched_at: str | None = None) -> dict[str, Any]:
        account_root = self._account_root(account_email)
        thread_root = os.path.join(account_root, "threads")
        os.makedirs(thread_root, exist_ok=True)
        now = fetched_at or _now()
        index = self._read_index(account_email)
        rows_by_ref = {
            str(row.get("source_ref")): row
            for row in index.get("threads", [])
            if row.get("source_ref")
        }

        for thread in threads:
            snapshot = _snapshot_thread(thread, fetched_at=now)
            source_ref = snapshot["source_ref"]
            payload = {
                "version": SNAPSHOT_VERSION,
                "provider": "gmail",
                "source_ref": source_ref,
                "fetched_at": now,
                "thread": snapshot,
            }
            self._atomic_write_json(self._thread_path(account_email, source_ref), payload)
            rows_by_ref[source_ref] = {
                "source_ref": source_ref,
                "subject": snapshot["subject"],
                "sender": snapshot["sender"],
                "received_at": snapshot["received_at"],
                "fetched_at": now,
                "attachment_count": len(snapshot["attachments"]),
            }

        rows = sorted(rows_by_ref.values(), key=lambda item: str(item.get("received_at") or ""), reverse=True)
        next_index = {
            "version": SNAPSHOT_VERSION,
            "provider": "gmail",
            "account_hash": self._account_hash(account_email),
            "updated_at": now,
            "threads": rows,
        }
        self._atomic_write_json(self._index_path(account_email), next_index)
        return {"stored_count": len(threads), "cached_count": len(rows), "updated_at": now}

    def _read_index(self, account_email: str) -> dict[str, Any]:
        path = self._index_path(account_email)
        if not os.path.exists(path):
            return {"version": SNAPSHOT_VERSION, "provider": "gmail", "threads": []}
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return {"version": SNAPSHOT_VERSION, "provider": "gmail", "threads": []}
        threads = data.get("threads")
        if not isinstance(threads, list):
            data["threads"] = []
        return data

    def _index_path(self, account_email: str) -> str:
        return os.path.join(self._account_root(account_email), "index.json")

    def _thread_path(self, account_email: str, source_ref: str) -> str:
        _assert_source_ref(source_ref)
        path = os.path.join(self._account_root(account_email), "threads", f"{_source_ref_filename(source_ref)}.json")
        return self._assert_cache_child(path)

    def _account_root(self, account_email: str) -> str:
        path = os.path.join(self.cache_root, self._account_hash(account_email))
        return self._assert_cache_child(path)

    def _account_hash(self, account_email: str) -> str:
        normalized = str(account_email or "unknown").strip().casefold()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]

    def _atomic_write_json(self, path: str, payload: dict[str, Any]) -> None:
        self._assert_cache_child(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, path)

    def _assert_cache_child(self, path: str) -> str:
        cache_root = os.path.realpath(self.cache_root)
        candidate = os.path.realpath(path)
        if os.path.commonpath([cache_root, candidate]) != cache_root:
            raise MailSnapshotStoreError("mail snapshot path escapes cache root")
        return candidate


def _snapshot_thread(thread: dict[str, Any], *, fetched_at: str) -> dict[str, Any]:
    source_ref = str(thread.get("source_ref") or "").strip()
    _assert_source_ref(source_ref)
    metadata = thread.get("metadata") if isinstance(thread.get("metadata"), dict) else {}
    return {
        "source_ref": source_ref,
        "subject": str(thread.get("subject") or "(no subject)").strip(),
        "sender": str(thread.get("sender") or "unknown").strip(),
        "recipients": _string_list(thread.get("recipients") or []),
        "received_at": str(thread.get("received_at") or fetched_at),
        "body": str(thread.get("body") or ""),
        "body_html": str(thread.get("body_html") or ""),
        "summary": str(thread.get("summary") or "").strip(),
        "attachments": [_snapshot_attachment(item) for item in thread.get("attachments") or []],
        "metadata": _safe_metadata(metadata | {"fetched_at": fetched_at}),
    }


def _snapshot_attachment(attachment: dict[str, Any]) -> dict[str, Any]:
    row = {
        "attachment_ref": str(attachment.get("attachment_ref") or "").strip(),
        "title": str(attachment.get("title") or attachment.get("name") or "attachment").strip(),
        "extension": str(attachment.get("extension") or "").strip().lower(),
        "size_bytes": int(attachment.get("size_bytes") or attachment.get("size") or 0),
        "mime_type": str(attachment.get("mime_type") or attachment.get("mime") or "").strip(),
        "summary": str(attachment.get("summary") or attachment.get("content_summary") or "").strip(),
        "download_status": str(attachment.get("download_status") or "").strip(),
        "inbox_path": str(attachment.get("inbox_path") or "").strip(),
        "extract_status": str(attachment.get("extract_status") or "").strip(),
        "key_points": _string_list(attachment.get("key_points") or []),
        "content_profile": attachment.get("content_profile") if isinstance(attachment.get("content_profile"), dict) else {},
        "error_reason": str(attachment.get("error_reason") or "").strip(),
    }
    for key in ("_gmail_message_id", "_gmail_attachment_id"):
        if attachment.get(key):
            row[key] = str(attachment.get(key) or "")
    return row


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    blocked = ("token", "raw_gmail", "gmail_thread_id", "gmail_message_id", "attachment_id")
    rows: dict[str, Any] = {}
    for key, value in metadata.items():
        normalized_key = str(key).casefold()
        if any(part in normalized_key for part in blocked):
            continue
        rows[str(key)] = value
    rows["raw_available"] = False
    rows["source_kind"] = "gmail_thread"
    return rows


def _assert_source_ref(source_ref: str) -> None:
    if not SOURCE_REF_RE.fullmatch(source_ref):
        raise MailSnapshotStoreError("invalid Gmail source_ref")


def _source_ref_filename(source_ref: str) -> str:
    _assert_source_ref(source_ref)
    return source_ref.replace(":", "__")


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if str(item).strip()]


def _limit(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 50
    return max(1, min(parsed, 500))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
