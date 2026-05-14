from __future__ import annotations

from types import SimpleNamespace

from app.services.mail_incremental import filter_new_threads, latest_processed_received_at
from app.routers.mail import _merge_thread_payloads, _merge_thread_rows


def test_latest_processed_received_at_returns_latest_timestamp() -> None:
    rows = [
        SimpleNamespace(received_at="2026-05-12T01:00:00+00:00"),
        SimpleNamespace(received_at="2026-05-12T03:00:00+00:00"),
    ]

    assert latest_processed_received_at(rows) == "2026-05-12T03:00:00+00:00"


def test_filter_new_threads_uses_cutoff_and_processed_source_refs() -> None:
    threads = [
        {"source_ref": "gmail:new", "received_at": "2026-05-12T04:00:00+00:00"},
        {"source_ref": "gmail:processed", "received_at": "2026-05-12T05:00:00+00:00"},
        {"source_ref": "gmail:old", "received_at": "2026-05-12T02:00:00+00:00"},
    ]

    result = filter_new_threads(
        threads,
        since_received_at="2026-05-12T03:00:00+00:00",
        processed_source_refs={"gmail:processed"},
    )

    assert [thread["source_ref"] for thread in result] == ["gmail:new"]


def test_incremental_completion_merges_existing_and_new_threads() -> None:
    base = [
        {"source_ref": "gmail:old", "received_at": "2026-05-12T01:00:00+00:00", "subject": "기존 메일"},
        {"source_ref": "gmail:dup", "received_at": "2026-05-12T02:00:00+00:00", "subject": "기존 중복"},
    ]
    new = [
        {"source_ref": "gmail:new", "received_at": "2026-05-12T04:00:00+00:00", "subject": "새 메일"},
        {"source_ref": "gmail:dup", "received_at": "2026-05-12T05:00:00+00:00", "subject": "새 중복"},
    ]

    result = _merge_thread_payloads(base, new)

    assert [thread["source_ref"] for thread in result] == ["gmail:dup", "gmail:new", "gmail:old"]
    assert result[0]["subject"] == "새 중복"


def test_incremental_row_merge_can_recover_source_run_chain() -> None:
    source_rows = [
        SimpleNamespace(source_ref="gmail:old", received_at="2026-05-12T01:00:00+00:00", subject="기존 메일"),
    ]
    incremental_rows = [
        SimpleNamespace(source_ref="gmail:new", received_at="2026-05-12T04:00:00+00:00", subject="새 메일"),
    ]

    result = _merge_thread_rows(source_rows, incremental_rows)

    assert [thread.source_ref for thread in result] == ["gmail:new", "gmail:old"]
