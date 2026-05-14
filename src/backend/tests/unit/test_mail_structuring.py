from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from app.services.mail_structuring import MailStructuringService, _build_prompt


def test_mail_structuring_parses_json_response() -> None:
    client = _Client({
        "threads": [
            {
                "source_ref": "gmail:t1",
                "summary": "견적 회신 요청",
                "category": "영업",
                "extracted_actions": [{"text": "견적 회신", "owner": "", "due_date": ""}],
                "extracted_due_dates": [],
                "structure_warnings": [],
                "confidence": 0.9,
            }
        ]
    })
    service = MailStructuringService(client_factory=lambda: client)

    result = asyncio.run(service.structure_threads([_thread("gmail:t1")]))

    assert result.structured_by_ref["gmail:t1"]["category"] == "영업"
    assert result.structured_by_ref["gmail:t1"]["extracted_actions"][0]["text"] == "견적 회신"
    assert result.warning_count == 0


def test_mail_structuring_falls_back_when_json_is_invalid() -> None:
    service = MailStructuringService(client_factory=lambda: _BrokenClient())

    result = asyncio.run(service.structure_threads([_thread("gmail:t1")]))

    structured = result.structured_by_ref["gmail:t1"]
    assert structured["summary"] == "기존 요약"
    assert structured["confidence"] == 0.0
    assert structured["structure_warnings"][0].startswith("LLM 구조화 fallback:")
    assert result.warning_count == 1


def test_mail_structuring_batches_and_limits_body_sample() -> None:
    threads = [_thread(f"gmail:t{i}", body="x" * 2000) for i in range(11)]
    client = _Client({"threads": []})
    service = MailStructuringService(client_factory=lambda: client, batch_size=10)

    asyncio.run(service.structure_threads(threads))
    prompt = _build_prompt([threads[0]])

    assert client.calls == 2
    assert "x" * 1500 not in prompt


class _Client:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0
        self.models = self

    def generate_content(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(text=json.dumps(self.payload, ensure_ascii=False))


class _BrokenClient:
    models: "_BrokenClient"

    def __init__(self) -> None:
        self.models = self

    def generate_content(self, **_kwargs):
        return SimpleNamespace(text="not json")


def _thread(source_ref: str, body: str = "본문") -> dict:
    return {
        "source_ref": source_ref,
        "subject": "견적 문의",
        "sender": "sales@example.com",
        "recipients": ["me@example.com"],
        "received_at": "2026-05-12T00:00:00+00:00",
        "summary": "기존 요약",
        "body": body,
        "attachments": [],
    }
