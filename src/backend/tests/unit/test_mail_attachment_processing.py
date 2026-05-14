from __future__ import annotations

import asyncio
from pathlib import Path

import app.services.mail_attachment_processing as processor_module
from app.services.mail_attachment_processing import MailAttachmentProcessor
from app.services.workspace_file_helpers import full_path


class FakeGmailFetcher:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.calls: list[dict] = []

    async def download_attachment(self, **kwargs) -> bytes:
        self.calls.append(kwargs)
        return self.content


def test_processor_downloads_text_attachment_to_inbox_and_summarizes(tmp_path, monkeypatch) -> None:
    async def fake_update_file_summary(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(processor_module, "update_file_summary", fake_update_file_summary)
    fetcher = FakeGmailFetcher("첨부 파일의 핵심 내용입니다.\n다음 조치가 필요합니다.".encode("utf-8"))
    threads = [{
        "source_ref": "gmail:t1",
        "subject": "첨부 확인 요청",
        "sender": "sender@example.com",
        "recipients": ["me@example.com"],
        "received_at": "2026-05-13T01:00:00+00:00",
        "body": "첨부 확인 부탁드립니다.",
        "attachments": [{
            "attachment_ref": "gmail:a1",
            "title": "request.txt",
            "extension": "txt",
            "mime_type": "text/plain",
            "size_bytes": 20,
            "_gmail_message_id": "m1",
            "_gmail_attachment_id": "a1",
        }],
    }]

    stats = asyncio.run(MailAttachmentProcessor().process_threads(
        workspace_path=str(tmp_path),
        user_id="user-1",
        token_ref="gmail:token",
        account_email="me@example.com",
        threads=threads,
        gmail_fetcher=fetcher,
        management_policy={},
    ))

    attachment = threads[0]["attachments"][0]
    saved = full_path(str(tmp_path), attachment["inbox_path"])
    assert Path(saved).read_text(encoding="utf-8") == "첨부 파일의 핵심 내용입니다.\n다음 조치가 필요합니다."
    assert attachment["download_status"] == "downloaded"
    assert attachment["extract_status"] == "summarized"
    assert "텍스트 파일입니다" in attachment["summary"]
    assert stats.downloaded_count == 1
    assert stats.summarized_count == 1
    assert fetcher.calls[0]["message_id"] == "m1"


def test_processor_skips_deterministic_blacklist_download(tmp_path, monkeypatch) -> None:
    async def fake_update_file_summary(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(processor_module, "update_file_summary", fake_update_file_summary)
    fetcher = FakeGmailFetcher(b"secret")
    threads = [{
        "source_ref": "gmail:t1",
        "subject": "뉴스레터",
        "sender": "news@example.com",
        "recipients": ["me@example.com"],
        "received_at": "2026-05-13T01:00:00+00:00",
        "attachments": [{
            "attachment_ref": "gmail:a1",
            "title": "news.pdf",
            "extension": "pdf",
            "_gmail_message_id": "m1",
            "_gmail_attachment_id": "a1",
        }],
    }]

    stats = asyncio.run(MailAttachmentProcessor().process_threads(
        workspace_path=str(tmp_path),
        user_id="user-1",
        token_ref="gmail:token",
        account_email="me@example.com",
        threads=threads,
        gmail_fetcher=fetcher,
        management_policy={
            "blacklist_rules": [{"field": "subject", "operator": "contains", "value": "뉴스레터"}],
        },
    ))

    assert fetcher.calls == []
    assert threads[0]["attachments"][0]["download_status"] == "skipped_excluded"
    assert stats.downloaded_count == 0
