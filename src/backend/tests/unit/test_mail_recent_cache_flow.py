from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.routers import mail as mail_router
from app.services.gmail_fetcher import GmailFetchResult


def test_recent_thread_payloads_uses_cache_without_fetch_when_sufficient(tmp_path, monkeypatch) -> None:
    store = mail_router.MailSnapshotStore(str(tmp_path))
    store.upsert_threads("me@example.com", [_thread("gmail:t1", "Cached", "2026-05-12T00:00:00+00:00")])
    fetcher = _Fetcher([])
    monkeypatch.setattr(mail_router, "_gmail_fetcher", lambda: fetcher)

    result = asyncio.run(mail_router._recent_thread_payloads(
        _project(tmp_path),
        _user(),
        _connection(),
        mail_router.AnalyzeRecentRequest(max_threads=1),
    ))

    assert fetcher.calls == 0
    assert result.threads[0]["subject"] == "Cached"
    assert result.cache_status["source"] == "cache"
    assert result.cache_status["hit"] is True


def test_recent_thread_payloads_fetches_and_stores_when_cache_is_short(tmp_path, monkeypatch) -> None:
    fetcher = _Fetcher([_thread("gmail:t1", "Fetched", "2026-05-12T00:00:00+00:00")])
    monkeypatch.setattr(mail_router, "_gmail_fetcher", lambda: fetcher)

    result = asyncio.run(mail_router._recent_thread_payloads(
        _project(tmp_path),
        _user(),
        _connection(),
        mail_router.AnalyzeRecentRequest(max_threads=1),
    ))
    cached = mail_router.MailSnapshotStore(str(tmp_path)).load_recent_threads("me@example.com", 1)

    assert fetcher.calls == 1
    assert result.threads[0]["subject"] == "Fetched"
    assert cached[0]["subject"] == "Fetched"
    assert result.fetched_at == "2026-05-12T01:00:00+00:00"
    assert result.cache_status["source"] == "cache_miss"


def test_recent_thread_payloads_force_refresh_fetches_even_with_cache(tmp_path, monkeypatch) -> None:
    store = mail_router.MailSnapshotStore(str(tmp_path))
    store.upsert_threads("me@example.com", [_thread("gmail:t1", "Cached", "2026-05-11T00:00:00+00:00")])
    fetcher = _Fetcher([_thread("gmail:t2", "Fetched", "2026-05-12T00:00:00+00:00")])
    monkeypatch.setattr(mail_router, "_gmail_fetcher", lambda: fetcher)

    result = asyncio.run(mail_router._recent_thread_payloads(
        _project(tmp_path),
        _user(),
        _connection(),
        mail_router.AnalyzeRecentRequest(max_threads=1, force_refresh=True),
    ))

    assert fetcher.calls == 1
    assert result.threads[0]["subject"] == "Fetched"
    assert result.cache_status["source"] == "gmail_fetch"
    assert result.cache_status["force_refresh"] is True


def test_thread_snapshot_detail_uses_cached_body_and_attachments(tmp_path) -> None:
    store = mail_router.MailSnapshotStore(str(tmp_path))
    store.upsert_threads(
        "me@example.com",
        [
            {
                **_thread("gmail:t1", "Cached", "2026-05-12T00:00:00+00:00"),
                "body": "메일 전문입니다.",
                "body_html": "<!doctype html><html><body><p>메일 원본입니다.</p></body></html>",
                "attachments": [
                    {
                        "title": "report.pdf",
                        "extension": "pdf",
                        "size_bytes": 123,
                        "mime_type": "application/pdf",
                        "summary": "리포트 요약",
                    }
                ],
            }
        ],
    )
    staging = SimpleNamespace(
        source_ref="gmail:t1",
        attachments_json="[]",
        metadata_json='{"body_sample":"짧은 샘플"}',
    )

    detail = mail_router._thread_snapshot_detail(_project(tmp_path), _user(), staging, _connection())

    assert detail["body"] == "메일 전문입니다."
    assert detail["body_source"] == "snapshot"
    assert "메일 원본입니다." in detail["body_html"]
    assert detail["body_html_source"] == "snapshot"
    assert detail["attachments"][0]["title"] == "report.pdf"
    assert detail["attachments"][0]["summary"] == "리포트 요약"
    assert detail["attachment_source"] == "snapshot"


def test_thread_snapshot_detail_falls_back_to_staging_sample(tmp_path) -> None:
    staging = SimpleNamespace(
        source_ref="gmail:missing",
        attachments_json="[]",
        metadata_json='{"body_sample":"짧은 샘플"}',
    )

    detail = mail_router._thread_snapshot_detail(_project(tmp_path), _user(), staging, None)

    assert detail["body"] == "짧은 샘플"
    assert detail["body_source"] == "staging_sample"
    assert detail["body_truncated"] is True
    assert detail["body_html"] == ""
    assert detail["body_html_source"] == "none"
    assert detail["attachment_source"] == "staging"


class _Fetcher:
    def __init__(self, threads: list[dict]) -> None:
        self.threads = threads
        self.calls = 0

    async def fetch_recent_threads(self, **_kwargs) -> GmailFetchResult:
        self.calls += 1
        return GmailFetchResult(threads=self.threads, fetched_at="2026-05-12T01:00:00+00:00")


def _project(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(id="project-1", workspace_path=str(tmp_path))


def _user() -> SimpleNamespace:
    return SimpleNamespace(id="user-1", email="me@example.com")


def _connection() -> SimpleNamespace:
    return SimpleNamespace(status="connected", token_ref="gmail:token", email="me@example.com")


def _thread(source_ref: str, subject: str, received_at: str) -> dict:
    return {
        "source_ref": source_ref,
        "subject": subject,
        "sender": "sender@example.com",
        "recipients": ["me@example.com"],
        "received_at": received_at,
        "body": "body",
        "body_html": "",
        "summary": "summary",
        "attachments": [],
        "metadata": {"source_kind": "gmail_thread"},
    }
