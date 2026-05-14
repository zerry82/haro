from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.mail_insights import build_mail_insights


def test_build_mail_insights_summarizes_threads_without_raw_body() -> None:
    result = build_mail_insights([
        _thread(
            "t1",
            sender="client@example.com",
            category="보고",
            attachments=[{"title": "report.pdf", "summary": "성과 보고"}],
            due_dates=[{"date": "2026-05-15", "text": "금요일까지"}],
        ),
        _thread(
            "t2",
            sender="client@example.com",
            category="보고",
            warnings=["요청 주체가 애매함"],
        ),
    ])

    assert "thread 2개" in result["summary"]
    assert {item["type"] for item in result["insights"]} >= {"top_sender", "due_dates", "structure_warnings"}
    serialized = json.dumps(result, ensure_ascii=False)
    assert "raw body" not in serialized
    assert "client@example.com" in serialized


def _thread(
    thread_id: str,
    *,
    sender: str,
    category: str,
    attachments: list[dict] | None = None,
    actions: list[dict] | None = None,
    due_dates: list[dict] | None = None,
    warnings: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=thread_id,
        subject=f"Subject {thread_id}",
        sender=sender,
        category=category,
        summary="summary",
        attachments_json=json.dumps(attachments or [], ensure_ascii=False),
        metadata_json=json.dumps(
            {
                "extracted_actions": actions or [],
                "extracted_due_dates": due_dates or [],
                "structure_warnings": warnings or [],
                "body": "raw body should never be used",
            },
            ensure_ascii=False,
        ),
    )
