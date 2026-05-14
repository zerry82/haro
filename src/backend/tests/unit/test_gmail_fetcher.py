from __future__ import annotations

import asyncio
import base64
import time

import httpx

from app.services.gmail_fetcher import GmailFetcher, _body_html, _body_text, normalize_mail_body_text
from app.services.gmail_oauth import EncryptedTokenStore


def test_gmail_fetcher_lists_threads_and_normalizes_payload(tmp_path) -> None:
    store = EncryptedTokenStore(str(tmp_path), "encryption-secret")
    store.store("gmail:c1", {"tokens": {"access_token": "access-1", "expires_at": int(time.time()) + 3600}})
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        assert request.headers["Authorization"] == "Bearer access-1"
        if request.url.path.endswith("/users/me/messages"):
            assert "q" not in request.url.params
            assert request.url.params["maxResults"] == "10"
        if request.url.path.endswith("/users/me/messages") and "pageToken" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {"id": "m1", "threadId": "t1"},
                        {"id": "m2", "threadId": "t1"},
                    ],
                    "nextPageToken": "next",
                },
            )
        if request.url.path.endswith("/users/me/messages"):
            return httpx.Response(200, json={"messages": [{"id": "m3", "threadId": "t2"}]})
        if request.url.path.endswith("/users/me/threads/t1"):
            return httpx.Response(200, json=_thread("t1", "m1", "성과 보고 요청", "client@example.com"))
        if request.url.path.endswith("/users/me/threads/t2"):
            return httpx.Response(200, json=_thread("t2", "m3", "계약서 확인", "legal@example.com"))
        raise AssertionError(f"unexpected request: {request.url}")

    fetcher = GmailFetcher(
        token_store=store,
        client_id="client-id",
        client_secret="client-secret",
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = asyncio.run(fetcher.fetch_recent_threads(token_ref="gmail:c1", account_email="me@example.com", max_threads=2))

    assert seen_paths.count("/gmail/v1/users/me/messages") == 2
    assert len(result.threads) == 2
    first = result.threads[0]
    assert first["subject"] in {"성과 보고 요청", "계약서 확인"}
    assert all(not thread["source_ref"].endswith("t1") for thread in result.threads)
    assert result.threads[0]["attachments"][0]["mime_type"] == "application/pdf"
    assert result.threads[0]["attachments"][0]["attachment_ref"].startswith("gmail:")
    assert result.threads[0]["attachments"][0]["_gmail_message_id"]
    assert result.threads[0]["attachments"][0]["_gmail_attachment_id"] == "a1"
    assert "본문 내용" in result.threads[0]["body"] or "본문 내용" in result.threads[1]["body"]


def test_gmail_fetcher_refreshes_expired_access_token(tmp_path) -> None:
    store = EncryptedTokenStore(str(tmp_path), "encryption-secret")
    store.store(
        "gmail:c1",
        {"tokens": {"access_token": "old-access", "refresh_token": "refresh-1", "expires_at": 1}},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "new-access", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer new-access"
        return httpx.Response(200, json={})

    fetcher = GmailFetcher(
        token_store=store,
        client_id="client-id",
        client_secret="client-secret",
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = asyncio.run(fetcher.fetch_recent_threads(token_ref="gmail:c1", account_email="me@example.com", max_threads=50))

    assert result.threads == []
    tokens = store.load("gmail:c1")["tokens"]
    assert tokens["access_token"] == "new-access"
    assert tokens["refresh_token"] == "refresh-1"
    assert tokens["expires_at"] > int(time.time())


def test_gmail_fetcher_converts_html_body_to_readable_lines() -> None:
    body = _body_text({
        "parts": [
            {
                "mimeType": "text/html",
                "body": {
                    "data": _b64(
                        "<html><head><style>.x{}</style></head><body>"
                        "<div>첫 문장입니다.</div><p>둘째 문장입니다.</p>"
                        "<ul><li>확인할 항목</li></ul>"
                        "</body></html>"
                    )
                },
            }
        ]
    })

    assert ".x" not in body
    assert "첫 문장입니다.\n둘째 문장입니다." in body
    assert "- 확인할 항목" in body


def test_gmail_fetcher_keeps_sandboxable_html_body() -> None:
    result = _body_html({
        "parts": [
            {
                "mimeType": "text/html",
                "body": {
                    "data": _b64(
                        "<html><body><style>p{color:red}</style>"
                        "<script>alert(1)</script>"
                        "<p onclick=\"alert(2)\">원본 모양</p>"
                        "<img src=\"https://tracker.example/pixel.png\">"
                        "</body></html>"
                    )
                },
            }
        ]
    })

    assert "Content-Security-Policy" in result
    assert "원본 모양" in result
    assert "p{color:red}" in result
    assert "script" not in result.casefold()
    assert "onclick" not in result.casefold()
    assert "tracker.example" not in result


def test_normalize_mail_body_text_splits_dense_paragraphs() -> None:
    dense = " ".join(["첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다."] * 25)

    body = normalize_mail_body_text(dense)

    assert "첫 문장입니다.\n둘째 문장입니다." in body
    assert max(len(line) for line in body.splitlines()) < len(dense)


def _thread(thread_id: str, message_id: str, subject: str, sender: str) -> dict:
    return {
        "id": thread_id,
        "snippet": "snippet",
        "messages": [
            {
                "id": message_id,
                "threadId": thread_id,
                "internalDate": "1770000000000",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": subject},
                        {"name": "From", "value": sender},
                        {"name": "To", "value": "me@example.com"},
                        {"name": "Date", "value": "Tue, 12 May 2026 10:00:00 +0900"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": _b64("본문 내용입니다.")},
                        },
                        {
                            "mimeType": "text/html",
                            "body": {"data": _b64("<p>본문 내용입니다.</p>")},
                        },
                        {
                            "filename": "report.pdf",
                            "mimeType": "application/pdf",
                            "body": {"attachmentId": "a1", "size": 1024},
                        },
                    ],
                },
            }
        ],
    }


def _b64(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
