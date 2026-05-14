from app.services.mail_analysis import analyze_mail_threads


def test_analyze_mail_threads_builds_stats_categories_and_attachment_summaries() -> None:
    result = analyze_mail_threads([
        {
            "source_ref": "thread-1",
            "subject": "이번 주 성과 보고서 요청",
            "sender": "manager@client.com",
            "recipients": ["owner@agency.com"],
            "received_at": "2026-05-01T01:00:00+00:00",
            "body": "이번 주 성과 보고서와 다음 액션을 보내주세요.",
            "attachments": [
                {
                    "title": "performance.xlsx",
                    "extension": "xlsx",
                    "size_bytes": 2048,
                    "summary": "성과 지표 표",
                }
            ],
        },
        {
            "source_ref": "thread-2",
            "subject": "Newsletter May",
            "sender": "news@vendor.com",
            "recipients": ["owner@agency.com"],
            "received_at": "2026-05-02T01:00:00+00:00",
            "body": "unsubscribe",
        },
    ])

    assert result["stats"]["thread_count"] == 2
    assert result["stats"]["sender_counts"][0] == {"sender": "manager@client.com", "count": 1}
    assert {"name": "보고/리포트", "count": 1} in result["stats"]["categories"]
    assert result["stats"]["attachments"] == [{
        "title": "performance.xlsx",
        "extension": "xlsx",
        "size_bytes": 2048,
        "mime_type": "",
        "summary": "성과 지표 표",
        "summarized": True,
        "key_points": ["성과 지표 표"],
        "extract_status": "summarized",
    }]
    assert result["threads"][0]["summary"] == "이번 주 성과 보고서와 다음 액션을 보내주세요."


def test_analyze_mail_threads_applies_filters_to_staging_decision() -> None:
    result = analyze_mail_threads(
        [
            {
                "subject": "Weekly report",
                "sender": "manager@client.com",
                "recipients": ["owner@agency.com"],
            },
            {
                "subject": "Newsletter",
                "sender": "news@vendor.com",
                "recipients": ["owner@agency.com"],
            },
        ],
        filters=[
            {"effect": "allow", "field": "sender", "operator": "domain_equals", "value": "client.com"},
            {"effect": "deny", "field": "subject", "operator": "contains", "value": "Newsletter"},
        ],
    )

    decisions = {thread["subject"]: thread["inclusion_decision"] for thread in result["threads"]}

    assert decisions == {"Weekly report": "allowed", "Newsletter": "denied"}
    assert result["stats"]["included_count"] == 1


def test_analyze_mail_threads_adds_structured_fields_and_counts() -> None:
    result = analyze_mail_threads(
        [
            {
                "source_ref": "thread-1",
                "subject": "계약서 검토 요청",
                "sender": "sales@example.com",
                "recipients": ["me@example.com"],
                "body": "금요일까지 계약서 검토 부탁드립니다.",
            }
        ],
        structured_by_ref={
            "thread-1": {
                "summary": "계약서 검토 요청",
                "category": "계약",
                "extracted_actions": [{"text": "계약서 검토", "owner": "me", "due_date": "2026-05-15"}],
                "extracted_due_dates": [{"date": "2026-05-15", "text": "금요일까지"}],
                "structure_warnings": ["상대 날짜 해석 필요"],
                "confidence": 0.72,
            }
        },
    )

    thread = result["threads"][0]

    assert thread["summary"] == "계약서 검토 요청"
    assert thread["category"] == "계약"
    assert thread["metadata"]["extracted_actions"] == [{"text": "계약서 검토", "owner": "me", "due_date": "2026-05-15"}]
    assert thread["metadata"]["confidence"] == 0.72
    assert result["stats"]["extracted_action_count"] == 1
    assert result["stats"]["due_date_count"] == 1
    assert result["stats"]["structure_warning_count"] == 1


def test_analyze_mail_threads_preserves_existing_category_when_reusing_staging_payload() -> None:
    result = analyze_mail_threads([
        {
            "source_ref": "thread-1",
            "subject": "짧은 제목",
            "sender": "sender@example.com",
            "recipients": ["me@example.com"],
            "summary": "이미 구조화된 요약",
            "category": "기존 카테고리",
            "metadata": {"extracted_actions": [{"text": "기존 요청"}]},
        }
    ])

    thread = result["threads"][0]

    assert thread["category"] == "기존 카테고리"
    assert thread["metadata"]["extracted_actions"] == [{"text": "기존 요청"}]
