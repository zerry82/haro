from __future__ import annotations

import json
from collections import Counter
from typing import Any


def build_mail_insights(threads: list[Any], query: str = "") -> dict[str, Any]:
    rows = [_thread_row(thread) for thread in threads]
    insights = [
        insight
        for insight in (
            _top_sender_insight(rows),
            _due_date_insight(rows),
            _attachment_insight(rows),
            _warning_insight(rows),
            _category_insight(rows),
        )
        if insight
    ]
    if query.strip():
        insights = _rank_for_query(insights, query)
    return {
        "summary": _summary(rows, insights),
        "insights": insights,
    }


def _top_sender_insight(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    counts = Counter(row["sender"] for row in rows if row["sender"])
    if not counts:
        return None
    sender, count = counts.most_common(1)[0]
    evidence = [row for row in rows if row["sender"] == sender][:5]
    return _insight(
        "top_sender",
        "반복 발신자",
        f"{sender}에서 온 thread가 {count}개로 가장 많습니다.",
        evidence,
        severity="info",
    )


def _due_date_insight(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    due_rows = [row for row in rows if row["due_dates"]]
    if not due_rows:
        return None
    return _insight(
        "due_dates",
        "마감이 있는 요청",
        f"마감 또는 일정 표현이 있는 thread가 {len(due_rows)}개입니다.",
        due_rows[:5],
        severity="warning" if len(due_rows) >= 5 else "info",
    )


def _attachment_insight(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    attachment_rows = [row for row in rows if row["attachments"]]
    if not attachment_rows:
        return None
    summarized_count = sum(
        1
        for row in attachment_rows
        for attachment in row["attachments"]
        if isinstance(attachment, dict) and attachment.get("summary")
    )
    return _insight(
        "attachments",
        "첨부파일 포함 thread",
        f"첨부파일이 있는 thread가 {len(attachment_rows)}개입니다. 내용 요약이 있는 첨부는 {summarized_count}개입니다.",
        attachment_rows[:5],
        severity="info",
    )


def _warning_insight(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    warning_rows = [row for row in rows if row["warnings"]]
    if not warning_rows:
        return None
    return _insight(
        "structure_warnings",
        "구조화 주의 항목",
        f"구조화 경고가 있는 thread가 {len(warning_rows)}개입니다.",
        warning_rows[:5],
        severity="warning",
    )


def _category_insight(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    counts = Counter(row["category"] for row in rows if row["category"])
    if not counts:
        return None
    category, count = counts.most_common(1)[0]
    return _insight(
        "top_category",
        "대표 카테고리",
        f"{category} 카테고리가 {count}개로 가장 많습니다.",
        [row for row in rows if row["category"] == category][:5],
        severity="info",
    )


def _insight(
    kind: str,
    title: str,
    summary: str,
    rows: list[dict[str, Any]],
    *,
    severity: str,
) -> dict[str, Any]:
    attachments = [
        attachment
        for row in rows
        for attachment in row["attachments"]
        if isinstance(attachment, dict)
    ][:5]
    return {
        "type": kind,
        "title": title,
        "summary": summary,
        "severity": severity,
        "thread_count": len(rows),
        "thread_ids": [row["id"] for row in rows],
        "attachments": attachments,
        "evidence": [
            {
                "thread_id": row["id"],
                "subject": row["subject"],
                "sender": row["sender"],
                "reason": _evidence_reason(row),
            }
            for row in rows
        ],
    }


def _thread_row(thread: Any) -> dict[str, Any]:
    metadata = _loads(getattr(thread, "metadata_json", ""), {})
    return {
        "id": str(getattr(thread, "id", "")),
        "subject": str(getattr(thread, "subject", "")),
        "sender": str(getattr(thread, "sender", "")),
        "category": str(getattr(thread, "category", "")),
        "summary": str(getattr(thread, "summary", "")),
        "attachments": _loads(getattr(thread, "attachments_json", ""), []),
        "actions": _list(metadata.get("extracted_actions")),
        "due_dates": _list(metadata.get("extracted_due_dates")),
        "warnings": _list(metadata.get("structure_warnings")),
    }


def _evidence_reason(row: dict[str, Any]) -> str:
    parts = []
    if row["actions"]:
        parts.append(f"요청 {len(row['actions'])}")
    if row["due_dates"]:
        parts.append(f"일정 {len(row['due_dates'])}")
    if row["attachments"]:
        parts.append(f"첨부 {len(row['attachments'])}")
    if row["warnings"]:
        parts.append(f"주의 {len(row['warnings'])}")
    return " · ".join(parts) or row["category"] or "thread 근거"


def _summary(rows: list[dict[str, Any]], insights: list[dict[str, Any]]) -> str:
    if not rows:
        return "분석된 Gmail thread가 없습니다."
    warning_count = sum(1 for row in rows if row["warnings"])
    due_count = sum(1 for row in rows if row["due_dates"])
    attachment_count = sum(1 for row in rows if row["attachments"])
    return (
        f"최근 분석 thread {len(rows)}개에서 인사이트 {len(insights)}개를 만들었습니다. "
        f"마감/일정 thread {due_count}개, 첨부 thread {attachment_count}개, 구조화 주의 thread {warning_count}개입니다."
    )


def _rank_for_query(insights: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    terms = [term for term in query.casefold().split() if len(term) >= 2]
    if not terms:
        return insights

    def score(insight: dict[str, Any]) -> int:
        haystack = json.dumps(insight, ensure_ascii=False).casefold()
        return sum(1 for term in terms if term in haystack)

    return sorted(insights, key=score, reverse=True)


def _loads(value: str, default: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
