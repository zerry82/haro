from __future__ import annotations

import json
import os

import pytest

from app.services.mail_snapshot_store import MailSnapshotStore, MailSnapshotStoreError


def test_mail_snapshot_store_upserts_and_loads_recent_threads(tmp_path) -> None:
    store = MailSnapshotStore(str(tmp_path))
    store.upsert_threads(
        "me@example.com",
        [
            _thread("gmail:old", "Old subject", "2026-05-10T00:00:00+00:00"),
            _thread("gmail:new", "New subject", "2026-05-12T00:00:00+00:00"),
        ],
        fetched_at="2026-05-12T01:00:00+00:00",
    )

    threads = store.load_recent_threads("me@example.com", 1)

    assert [thread["source_ref"] for thread in threads] == ["gmail:new"]
    assert threads[0]["subject"] == "New subject"
    assert threads[0]["body_html"] == "<p>본문</p>"
    assert threads[0]["metadata"]["source_kind"] == "gmail_thread"
    assert threads[0]["metadata"]["raw_available"] is False


def test_mail_snapshot_store_upsert_replaces_index_row_without_duplicates(tmp_path) -> None:
    store = MailSnapshotStore(str(tmp_path))

    store.upsert_threads("me@example.com", [_thread("gmail:t1", "First", "2026-05-10T00:00:00+00:00")])
    store.upsert_threads("me@example.com", [_thread("gmail:t1", "Changed", "2026-05-11T00:00:00+00:00")])

    threads = store.load_recent_threads("me@example.com", 10)
    index_path = next(tmp_path.glob(".haro/cache/mail/gmail/*/index.json"))
    index = json.loads(index_path.read_text(encoding="utf-8"))

    assert len(threads) == 1
    assert threads[0]["subject"] == "Changed"
    assert [row["source_ref"] for row in index["threads"]] == ["gmail:t1"]


def test_mail_snapshot_store_keeps_raw_gmail_ids_and_tokens_out_of_snapshot(tmp_path) -> None:
    store = MailSnapshotStore(str(tmp_path))
    store.upsert_threads(
        "me@example.com",
        [
            _thread(
                "gmail:t1",
                "Secret-ish",
                "2026-05-10T00:00:00+00:00",
                metadata={
                    "gmail_thread_id": "raw-thread-id",
                    "token": "secret",
                    "gmail_thread_ref": "gmail:safe-ref",
                },
            )
        ],
    )

    thread_path = next(tmp_path.glob(".haro/cache/mail/gmail/*/threads/*.json"))
    payload = json.loads(thread_path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload)

    assert "raw-thread-id" not in serialized
    assert "secret" not in serialized
    assert payload["thread"]["metadata"]["gmail_thread_ref"] == "gmail:safe-ref"


def test_mail_snapshot_store_rejects_invalid_source_ref(tmp_path) -> None:
    store = MailSnapshotStore(str(tmp_path))

    with pytest.raises(MailSnapshotStoreError):
        store.upsert_threads("me@example.com", [_thread("../escape", "Bad", "2026-05-10T00:00:00+00:00")])

    assert not os.path.exists(tmp_path / "escape.json")


def _thread(
    source_ref: str,
    subject: str,
    received_at: str,
    *,
    metadata: dict | None = None,
) -> dict:
    return {
        "source_ref": source_ref,
        "subject": subject,
        "sender": "sender@example.com",
        "recipients": ["me@example.com"],
        "received_at": received_at,
        "body": "본문",
        "body_html": "<p>본문</p>",
        "summary": "summary",
        "attachments": [
            {
                "title": "report.pdf",
                "extension": "pdf",
                "size_bytes": 123,
                "mime_type": "application/pdf",
            }
        ],
        "metadata": metadata or {},
    }
