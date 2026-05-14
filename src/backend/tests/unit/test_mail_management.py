from __future__ import annotations

from app.services.mail_management import (
    apply_management_to_thread,
    decide_management,
    enrich_attachment,
)


def test_whitelist_takes_priority_over_blacklist() -> None:
    thread = _thread(subject="광고 승인 요청", sender="partner@client.com")
    policy = {
        "whitelist_rules": [{"id": "w1", "field": "sender", "operator": "domain_equals", "value": "client.com"}],
        "blacklist_rules": [{"id": "b1", "field": "subject", "operator": "contains", "value": "광고"}],
    }

    decision = decide_management(thread, policy)

    assert decision.decision == "managed"
    assert decision.source == "whitelist"
    assert decision.matched_rule_ids == ["w1"]


def test_blacklist_excludes_only_when_whitelist_does_not_match() -> None:
    thread = _thread(subject="뉴스레터 이벤트", sender="news@vendor.com")
    policy = {
        "blacklist_rules": [{"id": "b1", "field": "subject", "operator": "contains", "value": "뉴스레터"}],
    }

    decision = decide_management(thread, policy)

    assert decision.decision == "excluded"
    assert decision.source == "blacklist"


def test_manual_override_wins_over_automatic_exclusion() -> None:
    thread = _thread(thread_id="thread-1", subject="뉴스레터 이벤트", sender="news@vendor.com")
    policy = {
        "blacklist_rules": [{"id": "b1", "field": "subject", "operator": "contains", "value": "뉴스레터"}],
        "manual_overrides": [{"thread_id": "thread-1", "decision": "managed", "reason": "업무 참고 자료"}],
    }

    decision = decide_management(thread, policy)

    assert decision.decision == "managed"
    assert decision.source == "manual_override"


def test_manual_override_can_follow_source_ref_across_runs() -> None:
    thread = _thread(thread_id="new-thread-id", subject="뉴스레터 이벤트", sender="news@vendor.com")
    policy = {
        "blacklist_rules": [{"id": "b1", "field": "subject", "operator": "contains", "value": "뉴스레터"}],
        "manual_overrides": [{"thread_id": "old-thread-id", "source_ref": "source-new-thread-id", "decision": "managed"}],
    }

    decision = decide_management(thread, policy)

    assert decision.decision == "managed"
    assert decision.source == "manual_override"


def test_attachment_centered_mail_gets_attachment_context_and_core_text() -> None:
    thread = _thread(
        body="첨부파일 확인 부탁드립니다.",
        attachments=[{
            "title": "proposal.pdf",
            "extension": "pdf",
            "size_bytes": 1200,
            "summary": "신규 제안서의 견적과 납기 일정",
        }],
    )

    result = apply_management_to_thread(thread, {})

    assert result["metadata"]["primary_context_source"] == "attachment"
    assert result["metadata"]["attachment_signals"]["summary_status"] == "summarized"
    assert "신규 제안서의 견적과 납기 일정" in result["metadata"]["mail_core_text"]
    assert result["attachments"][0]["extract_status"] == "summarized"


def test_image_attachment_is_supported_pending_until_extracted() -> None:
    attachment = enrich_attachment({"title": "image.png", "extension": "png", "size_bytes": 30})

    assert attachment["extract_status"] == "supported_pending"
    assert attachment["key_points"] == []


def _thread(
    *,
    thread_id: str = "thread-1",
    subject: str = "업무 메일",
    sender: str = "sender@example.com",
    body: str = "업무 내용을 확인해 주세요.",
    attachments: list[dict] | None = None,
) -> dict:
    return {
        "id": thread_id,
        "source_ref": f"source-{thread_id}",
        "subject": subject,
        "sender": sender,
        "recipients": ["me@example.com"],
        "body": body,
        "summary": body,
        "attachments": attachments or [],
        "metadata": {"body_sample": body},
    }
