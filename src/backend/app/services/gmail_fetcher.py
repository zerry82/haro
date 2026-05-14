from __future__ import annotations

import base64
import hashlib
import html
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

import httpx

from app.services.gmail_oauth import EncryptedTokenStore, TokenStoreError

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
BODY_LIMIT = 20_000
HTML_BODY_LIMIT = 200_000
BODY_DENSE_TEXT_MIN_LENGTH = 700
BODY_DENSE_LINE_LIMIT = 360
MAIL_HTML_CSP = (
    "default-src 'none'; "
    "img-src data: blob:; "
    "style-src 'unsafe-inline'; "
    "font-src data:; "
    "base-uri 'none'; "
    "form-action 'none'"
)


class GmailFetchError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class GmailAuthError(GmailFetchError):
    def __init__(self, message: str = "Gmail authorization is invalid or expired") -> None:
        super().__init__(message, status_code=401)


@dataclass(frozen=True)
class GmailFetchResult:
    threads: list[dict[str, Any]]
    fetched_at: str


class GmailFetcher:
    def __init__(
        self,
        *,
        token_store: EncryptedTokenStore,
        client_id: str,
        client_secret: str,
        timeout_seconds: float = 10.0,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self.token_store = token_store
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout_seconds = timeout_seconds
        self.client_factory = client_factory

    async def fetch_recent_threads(self, *, token_ref: str, account_email: str, max_threads: int = 50) -> GmailFetchResult:
        token_payload = self._load_token_payload(token_ref)
        access_token = await self._access_token(token_ref, token_payload)
        fetched_at = _now()
        thread_limit = _thread_limit(max_threads)

        async with self._client() as client:
            thread_ids = await self._list_recent_thread_ids(client, access_token, thread_limit)
            threads: list[dict[str, Any]] = []
            for thread_id in thread_ids:
                thread = await self._fetch_thread(client, access_token, thread_id)
                threads.append(_thread_payload(thread, account_email=account_email, fetched_at=fetched_at))

        threads.sort(key=lambda item: item["received_at"], reverse=True)
        return GmailFetchResult(threads=threads, fetched_at=fetched_at)

    async def download_attachment(self, *, token_ref: str, message_id: str, attachment_id: str) -> bytes:
        token_payload = self._load_token_payload(token_ref)
        access_token = await self._access_token(token_ref, token_payload)
        async with self._client() as client:
            response = await client.get(
                f"{GMAIL_API_BASE}/users/me/messages/{message_id}/attachments/{attachment_id}",
                headers=_auth_headers(access_token),
            )
        data = _json_or_fetch_error(response, "Failed to download Gmail attachment")
        encoded = str(data.get("data") or "")
        if not encoded:
            return b""
        try:
            padding = "=" * (-len(encoded) % 4)
            return base64.urlsafe_b64decode(encoded + padding)
        except (ValueError, TypeError) as exc:
            raise GmailFetchError("Failed to decode Gmail attachment") from exc

    async def _list_recent_thread_ids(self, client: httpx.AsyncClient, access_token: str, max_threads: int) -> list[str]:
        thread_ids: list[str] = []
        seen: set[str] = set()
        page_token: str | None = None
        page_size = min(max(max_threads * 2, 10), 100)
        while True:
            params: dict[str, Any] = {"maxResults": page_size}
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(
                f"{GMAIL_API_BASE}/users/me/messages",
                params=params,
                headers=_auth_headers(access_token),
            )
            data = _json_or_fetch_error(response, "Failed to list Gmail messages")
            for ref in data.get("messages") or []:
                thread_id = str(ref.get("threadId") or "").strip()
                if thread_id and thread_id not in seen:
                    seen.add(thread_id)
                    thread_ids.append(thread_id)
                    if len(thread_ids) >= max_threads:
                        return thread_ids
            page_token = data.get("nextPageToken")
            if not page_token:
                return thread_ids

    async def _fetch_thread(self, client: httpx.AsyncClient, access_token: str, thread_id: str) -> dict[str, Any]:
        response = await client.get(
            f"{GMAIL_API_BASE}/users/me/threads/{thread_id}",
            params={"format": "full"},
            headers=_auth_headers(access_token),
        )
        return _json_or_fetch_error(response, "Failed to fetch Gmail thread")

    async def _access_token(self, token_ref: str, token_payload: dict[str, Any]) -> str:
        tokens = _tokens(token_payload)
        access_token = str(tokens.get("access_token") or "")
        expires_at = int(tokens.get("expires_at") or 0)
        if access_token and (not expires_at or expires_at > int(time.time()) + 60):
            return access_token

        refresh_token = str(tokens.get("refresh_token") or "")
        if not refresh_token:
            if access_token:
                return access_token
            raise GmailAuthError()

        async with self._client() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={"Accept": "application/json"},
            )
        refreshed = _json_or_fetch_error(response, "Failed to refresh Gmail token")
        merged = {**tokens, **refreshed, "refresh_token": refresh_token}
        _stamp_expiry(merged)
        token_payload["tokens"] = merged
        token_payload["updated_at"] = _now()
        self.token_store.store(token_ref, token_payload)
        return str(merged.get("access_token") or "")

    def _load_token_payload(self, token_ref: str) -> dict[str, Any]:
        try:
            return self.token_store.load(token_ref)
        except TokenStoreError as exc:
            raise GmailAuthError("Gmail token is not available") from exc

    def _client(self) -> httpx.AsyncClient:
        if self.client_factory:
            return self.client_factory()
        return httpx.AsyncClient(timeout=self.timeout_seconds)


def _thread_payload(thread: dict[str, Any], *, account_email: str, fetched_at: str) -> dict[str, Any]:
    messages = thread.get("messages") or []
    parsed_messages = [_message_payload(message, account_email=account_email) for message in messages]
    parsed_messages.sort(key=lambda item: item["received_at"])
    latest = parsed_messages[-1] if parsed_messages else {}
    subject = str(latest.get("subject") or _first(parsed_messages, "subject") or "(no subject)")
    body = "\n\n".join(item["body"] for item in parsed_messages if item.get("body")).strip()
    body_html = _thread_body_html([item["body_html"] for item in parsed_messages if item.get("body_html")])
    attachments = [attachment for item in parsed_messages for attachment in item.get("attachments") or []]
    external_links = _unique(
        link
        for item in parsed_messages
        for link in _extract_links(f"{item.get('body') or ''}\n{item.get('body_html') or ''}")
    )[:20]
    thread_id = str(thread.get("id") or latest.get("thread_id") or "")
    message_ids = [item["message_id"] for item in parsed_messages if item.get("message_id")]

    return {
        "source_ref": _source_ref(account_email, thread_id),
        "subject": subject,
        "sender": str(latest.get("sender") or _first(parsed_messages, "sender") or "unknown"),
        "recipients": _unique(
            recipient
            for item in parsed_messages
            for recipient in item.get("recipients") or []
        ),
        "received_at": str(latest.get("received_at") or _now()),
        "body": body[:BODY_LIMIT],
        "body_html": body_html[:HTML_BODY_LIMIT],
        "summary": str(thread.get("snippet") or "").strip(),
        "attachments": attachments,
        "metadata": {
            "source_kind": "gmail_thread",
            "raw_available": False,
            "gmail_message_count": len(parsed_messages),
            "gmail_attachment_count": len(attachments),
            "gmail_thread_ref": _source_ref(account_email, thread_id),
            "gmail_message_refs": [_source_ref(account_email, message_id) for message_id in message_ids],
            "external_links": external_links,
            "fetched_at": fetched_at,
        },
    }


def _message_payload(message: dict[str, Any], *, account_email: str) -> dict[str, Any]:
    payload = message.get("payload") or {}
    headers = _headers(payload)
    body = _body_text(payload)
    body_html = _body_html(payload)
    message_id = str(message.get("id") or "")
    return {
        "message_id": message_id,
        "thread_id": str(message.get("threadId") or ""),
        "subject": headers.get("subject") or "(no subject)",
        "sender": headers.get("from") or "unknown",
        "recipients": _address_list([headers.get("to"), headers.get("cc")]),
        "received_at": _received_at(headers.get("date"), message.get("internalDate")),
        "body": body[:BODY_LIMIT],
        "body_html": body_html[:HTML_BODY_LIMIT],
        "attachments": _attachments(payload, account_email=account_email, message_id=message_id),
    }


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    rows = payload.get("headers") or []
    return {
        str(row.get("name") or "").casefold(): str(row.get("value") or "")
        for row in rows
        if row.get("name")
    }


def _body_text(payload: dict[str, Any]) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in _walk_parts(payload):
        mime_type = str(part.get("mimeType") or "").casefold()
        data = ((part.get("body") or {}).get("data") or "")
        if not data:
            continue
        decoded = _decode_body(data)
        if mime_type == "text/plain":
            plain_parts.append(decoded)
        elif mime_type == "text/html":
            html_parts.append(_html_to_text(decoded))
    plain_text = normalize_mail_body_text("\n".join(plain_parts))
    html_text = normalize_mail_body_text("\n".join(html_parts))
    if plain_text and (not _looks_like_dense_blob(plain_text) or not html_text):
        return plain_text
    return html_text or plain_text


def _body_html(payload: dict[str, Any]) -> str:
    html_parts: list[str] = []
    for part in _walk_parts(payload):
        mime_type = str(part.get("mimeType") or "").casefold()
        data = ((part.get("body") or {}).get("data") or "")
        if mime_type != "text/html" or not data:
            continue
        html_parts.append(_decode_body(data))
    if not html_parts:
        return ""
    return sanitize_mail_html("\n".join(html_parts))


def _attachments(payload: dict[str, Any], *, account_email: str, message_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for part in _walk_parts(payload):
        filename = str(part.get("filename") or "").strip()
        body = part.get("body") or {}
        attachment_id = str(body.get("attachmentId") or "").strip()
        if not filename:
            continue
        attachment_ref = _source_ref(account_email, f"{message_id}:{attachment_id}:{filename}")
        rows.append({
            "attachment_ref": attachment_ref,
            "title": filename,
            "extension": filename.rsplit(".", 1)[1].casefold() if "." in filename else "",
            "size_bytes": int(body.get("size") or 0),
            "mime_type": str(part.get("mimeType") or ""),
            "summary": "",
            "_gmail_message_id": message_id,
            "_gmail_attachment_id": attachment_id,
        })
    return rows


def _extract_links(value: str) -> list[str]:
    rows: list[str] = []
    for match in re.finditer(r"https?://[^\s\"'<>)]+", str(value or "")):
        link = html.unescape(match.group(0)).rstrip(".,;]")
        if link and link not in rows:
            rows.append(link)
    return rows


def _walk_parts(part: dict[str, Any]) -> list[dict[str, Any]]:
    children = part.get("parts") or []
    if not children:
        return [part]
    rows = [part]
    for child in children:
        rows.extend(_walk_parts(child))
    return rows


def _decode_body(data: str) -> str:
    try:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def _html_to_text(value: str) -> str:
    without_hidden = re.sub(r"(?is)<(head|script|style|svg|noscript).*?>.*?</\1>", "\n", value)
    with_breaks = re.sub(r"(?i)<br\s*/?>", "\n", without_hidden)
    with_breaks = re.sub(r"(?i)<li\b[^>]*>", "\n- ", with_breaks)
    with_breaks = re.sub(r"(?i)</(p|div|section|article|table|tr|h[1-6]|blockquote|li)>", "\n", with_breaks)
    without_tags = re.sub(r"(?s)<[^>]+>", " ", with_breaks)
    return normalize_mail_body_text(without_tags)


def sanitize_mail_html(value: str) -> str:
    document = str(value or "")
    document = re.sub(
        r"(?is)<(script|iframe|object|embed|form|input|button|textarea|select|base|link|meta).*?>.*?</\1>",
        " ",
        document,
    )
    document = re.sub(
        r"(?is)<(script|iframe|object|embed|form|input|button|textarea|select|base|link|meta)\b[^>]*?/?>",
        " ",
        document,
    )
    document = re.sub(r"(?is)\s+on[a-z0-9_-]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", document)
    document = re.sub(r"(?is)\s+(href|xlink:href)\s*=\s*(['\"]?)\s*javascript:[^'\"\s>]*\2", "", document)
    document = re.sub(r"(?is)\s+src\s*=\s*(['\"]?)\s*https?://[^'\"\s>]*\1", "", document)
    document = re.sub(r"(?is)\s+srcset\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", document)
    document = document[:HTML_BODY_LIMIT]
    return (
        "<!doctype html><html><head>"
        '<meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{html.escape(MAIL_HTML_CSP, quote=True)}">'
        "<style>"
        "html,body{margin:0;padding:0;background:#fff;color:#111827;"
        "font:14px/1.5 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}"
        "body{padding:12px;overflow-wrap:anywhere;}"
        "img{max-width:100%;height:auto;}"
        "table{max-width:100%;border-collapse:collapse;}"
        "a{color:#2563eb;}"
        "</style>"
        "</head><body>"
        f"{document}"
        "</body></html>"
    )


def normalize_mail_body_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\u200b-\u200d\ufeff]", "", text)
    lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in text.splitlines()]
    normalized = "\n".join(line for line in lines if line)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    return _split_dense_paragraphs(normalized)


def _split_dense_paragraphs(text: str) -> str:
    if not _looks_like_dense_blob(text):
        return text
    with_sentence_breaks = re.sub(r"(?<=[.!?。！？])\s+(?=\S)", "\n", text)
    with_list_breaks = re.sub(r"\s+([•▪▶※*-]\s+)", r"\n\1", with_sentence_breaks)
    return re.sub(r"\n{3,}", "\n\n", with_list_breaks).strip()


def _looks_like_dense_blob(text: str) -> bool:
    if len(text) < BODY_DENSE_TEXT_MIN_LENGTH:
        return False
    nonempty_lines = [line for line in text.splitlines() if line.strip()]
    if not nonempty_lines:
        return False
    return len(nonempty_lines) <= 3 or max(len(line) for line in nonempty_lines) > BODY_DENSE_LINE_LIMIT


def _thread_body_html(html_parts: list[str]) -> str:
    if not html_parts:
        return ""
    if len(html_parts) == 1:
        return html_parts[0]
    body_parts = []
    for index, part in enumerate(html_parts, start=1):
        body_parts.append(
            "<section style=\"border-bottom:1px solid #e5e7eb;margin-bottom:16px;padding-bottom:16px;\">"
            f"<div style=\"font-size:12px;color:#6b7280;margin-bottom:8px;\">Message {index}</div>"
            f"{_extract_body_inner(part)}"
            "</section>"
        )
    return sanitize_mail_html("\n".join(body_parts))


def _extract_body_inner(document: str) -> str:
    match = re.search(r"(?is)<body\b[^>]*>(.*?)</body>", document or "")
    return match.group(1) if match else document


def _received_at(date_header: str | None, internal_date: Any) -> str:
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
    try:
        return datetime.fromtimestamp(int(internal_date) / 1000, timezone.utc).isoformat()
    except (TypeError, ValueError):
        return _now()


def _json_or_fetch_error(response: httpx.Response, message: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code in {401, 403}:
        detail = _error_detail(data) or response.text
        raise GmailAuthError(detail)
    if response.status_code >= 400:
        detail = _error_detail(data) or response.text
        raise GmailFetchError(f"{message}: {detail}")
    if not isinstance(data, dict):
        raise GmailFetchError(message)
    return data


def _error_detail(data: dict[str, Any]) -> str:
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error.get("status") or "")
    return str(error or "")


def _tokens(token_payload: dict[str, Any]) -> dict[str, Any]:
    tokens = token_payload.get("tokens") or {}
    if not isinstance(tokens, dict):
        raise GmailAuthError("Gmail token payload is invalid")
    return tokens


def _stamp_expiry(tokens: dict[str, Any]) -> None:
    try:
        expires_in = int(tokens.get("expires_in") or 0)
    except (TypeError, ValueError):
        expires_in = 0
    if expires_in:
        tokens["expires_at"] = int(time.time()) + expires_in


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}


def _address_list(values: list[str | None]) -> list[str]:
    rows: list[str] = []
    for value in values:
        if not value:
            continue
        rows.extend(part.strip() for part in value.split(",") if part.strip())
    return _unique(rows)


def _unique(values: Any) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            rows.append(item)
    return rows


def _first(rows: list[dict[str, Any]], key: str) -> Any:
    for row in rows:
        value = row.get(key)
        if value:
            return value
    return None


def _source_ref(account_email: str, source_id: str) -> str:
    digest = hashlib.sha256(f"{account_email}\n{source_id}".encode("utf-8")).hexdigest()[:24]
    return f"gmail:{digest}"


def _thread_limit(max_threads: int) -> int:
    try:
        value = int(max_threads)
    except (TypeError, ValueError):
        value = 50
    return max(1, min(value, 500))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
