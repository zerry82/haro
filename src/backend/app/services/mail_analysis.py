from __future__ import annotations

import hashlib
import os
from collections import Counter
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Any

from app.services.mail_filtering import evaluate_mail_filters
from app.services.mail_management import apply_management_policy

SUMMARIZABLE_EXTENSIONS = {"txt", "md", "ppt", "pptx", "pdf", "xls", "xlsx", "csv", "png", "jpeg", "jpg"}


def recent_count_range(max_threads: int = 50) -> tuple[str, str]:
    end = datetime.now(timezone.utc)
    return f"latest:{max_threads}", end.isoformat()


def analyze_mail_threads(
    threads: list[dict[str, Any]],
    filters: list[dict[str, Any]] | None = None,
    categories: list[dict[str, Any]] | None = None,
    structured_by_ref: dict[str, dict[str, Any]] | None = None,
    management_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    structured = structured_by_ref or {}
    staging_threads = [
        _normalize_thread(thread, filters or [], categories or [], structured.get(str(thread.get("source_ref") or "")))
        for thread in threads
    ]
    staging_threads = apply_management_policy(staging_threads, management_policy)
    sender_counts = Counter(thread["sender"] for thread in staging_threads)
    category_counts = Counter(thread["category"] for thread in staging_threads)
    attachment_rows = [
        attachment
        for thread in staging_threads
        for attachment in thread["attachments"]
    ]
    action_count = sum(len(thread["metadata"].get("extracted_actions") or []) for thread in staging_threads)
    due_date_count = sum(len(thread["metadata"].get("extracted_due_dates") or []) for thread in staging_threads)
    warning_count = sum(len(thread["metadata"].get("structure_warnings") or []) for thread in staging_threads)
    managed_count = sum(1 for thread in staging_threads if thread["metadata"].get("management_decision") == "managed")
    excluded_count = sum(1 for thread in staging_threads if thread["metadata"].get("management_decision") == "excluded")
    attachment_primary_count = sum(1 for thread in staging_threads if thread["metadata"].get("primary_context_source") == "attachment")
    manual_managed_count = sum(1 for thread in staging_threads if thread["metadata"].get("decision_source") == "manual_override")
    llm_excluded_count = sum(1 for thread in staging_threads if thread["metadata"].get("decision_source") == "llm_blacklist")
    proposed_categories = _proposed_categories(staging_threads, categories or [])

    stats = {
        "received_count": len(staging_threads),
        "thread_count": len(staging_threads),
        "included_count": sum(1 for thread in staging_threads if thread["inclusion_decision"] == "allowed"),
        "extracted_action_count": action_count,
        "due_date_count": due_date_count,
        "structure_warning_count": warning_count,
        "managed_count": managed_count,
        "excluded_count": excluded_count,
        "attachment_primary_count": attachment_primary_count,
        "manual_managed_count": manual_managed_count,
        "llm_excluded_count": llm_excluded_count,
        "sender_counts": [{"sender": sender, "count": count} for sender, count in sender_counts.most_common()],
        "topic_counts": [{"topic": category, "count": count} for category, count in category_counts.most_common()],
        "attachments": attachment_rows,
        "categories": [{"name": category, "count": count} for category, count in category_counts.most_common()],
    }

    return {
        "stats": stats,
        "proposed_categories": proposed_categories,
        "proposed_filters": _proposed_filters(staging_threads),
        "threads": staging_threads,
    }


def thread_payload_from_staging(staging: Any) -> dict[str, Any]:
    return {
        "source_ref": staging.source_ref,
        "subject": staging.subject,
        "sender": staging.sender,
        "recipients": _json_or_empty_list(staging.recipients_json),
        "received_at": staging.received_at,
        "summary": staging.summary,
        "category": staging.category,
        "attachments": _json_or_empty_list(staging.attachments_json),
        "metadata": _json_or_empty_dict(staging.metadata_json),
    }


def _normalize_thread(
    thread: dict[str, Any],
    filters: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    structured: dict[str, Any] | None = None,
) -> dict[str, Any]:
    subject = str(thread.get("subject") or "(no subject)").strip()
    sender = str(thread.get("sender") or "unknown").strip()
    recipients = _string_list(thread.get("recipients") or [])
    body = str(thread.get("body") or "")
    structured = structured if isinstance(structured, dict) else {}
    summary = str(structured.get("summary") or thread.get("summary") or _summarize_text(body) or subject)
    received_at = str(thread.get("received_at") or datetime.now(timezone.utc).isoformat())
    source_ref = str(thread.get("source_ref") or _source_ref(subject, sender, received_at))
    category = str(structured.get("category") or thread.get("category") or _category_for_thread(subject, body, categories)).strip() or "일반 업무"
    attachments = [_normalize_attachment(attachment) for attachment in thread.get("attachments") or []]
    evaluation = evaluate_mail_filters(
        {"subject": subject, "sender": sender, "recipients": recipients},
        filters,
    )

    input_metadata = thread.get("metadata") if isinstance(thread.get("metadata"), dict) else {}
    extracted_actions = _dict_list(
        structured.get("extracted_actions") if structured else input_metadata.get("extracted_actions")
    )
    extracted_due_dates = _dict_list(
        structured.get("extracted_due_dates") if structured else input_metadata.get("extracted_due_dates")
    )
    structure_warnings = _string_list(
        structured.get("structure_warnings") if structured else input_metadata.get("structure_warnings") or []
    )
    confidence = _confidence_or_none(structured.get("confidence") if structured else input_metadata.get("confidence"))
    return {
        "source_ref": source_ref,
        "subject": subject,
        "sender": sender,
        "sender_domain": _sender_domain(sender),
        "recipients": recipients,
        "received_at": received_at,
        "summary": summary,
        "category": category,
        "attachments": attachments,
        "inclusion_decision": evaluation.decision,
        "matched_filter_ids": evaluation.matched_filter_ids,
        "metadata": {
            **input_metadata,
            "source_kind": "gmail_thread",
            "raw_available": False,
            "body_sample": _summarize_text(body, limit=180),
            "extracted_actions": extracted_actions,
            "extracted_due_dates": extracted_due_dates,
            "structure_warnings": structure_warnings,
            "confidence": confidence,
            "llm_structured": bool(structured) or bool(input_metadata.get("llm_structured")),
        },
    }


def _normalize_attachment(attachment: dict[str, Any]) -> dict[str, Any]:
    title = str(attachment.get("title") or attachment.get("name") or "attachment").strip()
    extension = str(attachment.get("extension") or os.path.splitext(title)[1].lstrip(".")).lower()
    size_bytes = int(attachment.get("size_bytes") or attachment.get("size") or 0)
    provided_summary = str(attachment.get("summary") or attachment.get("content_summary") or "").strip()
    summary = provided_summary if extension in SUMMARIZABLE_EXTENSIONS else ""
    row = {
        "title": title,
        "extension": extension,
        "size_bytes": size_bytes,
        "mime_type": str(attachment.get("mime_type") or attachment.get("mime") or "").strip(),
        "summary": summary,
        "summarized": bool(summary),
    }
    for key in (
        "attachment_ref",
        "download_status",
        "inbox_path",
        "extract_status",
        "key_points",
        "content_profile",
        "error_reason",
    ):
        if key in attachment:
            row[key] = attachment[key]
    row.setdefault(
        "extract_status",
        "summarized" if summary else ("supported_pending" if extension in SUMMARIZABLE_EXTENSIONS else "metadata_only"),
    )
    row.setdefault("key_points", _string_list(attachment.get("key_points") or []))
    return row


def _category_for_thread(subject: str, body: str, categories: list[dict[str, Any]]) -> str:
    haystack = f"{subject}\n{body}".casefold()
    for category in categories:
        name = str(category.get("name") or "").strip()
        keywords = [str(keyword).casefold() for keyword in category.get("keywords") or [] if str(keyword).strip()]
        if name and keywords and any(keyword in haystack for keyword in keywords):
            return name
    if any(keyword in haystack for keyword in ("report", "보고", "리포트", "성과")):
        return "보고/리포트"
    if any(keyword in haystack for keyword in ("meeting", "회의", "미팅", "schedule", "일정")):
        return "일정/회의"
    if any(keyword in haystack for keyword in ("contract", "계약", "invoice", "정산", "세금계산서")):
        return "계약/정산"
    if any(keyword in haystack for keyword in ("newsletter", "뉴스레터", "unsubscribe")):
        return "뉴스레터"
    return "일반 업무"


def _proposed_categories(staging_threads: list[dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_names = {str(category.get("name") or "").strip() for category in existing}
    counts = Counter(thread["category"] for thread in staging_threads)
    proposals = [{"name": name, "count": count, "confirmed": name in existing_names} for name, count in counts.most_common()]
    if proposals:
        return proposals
    return [{"name": "일반 업무", "count": 0, "confirmed": False}]


def _proposed_filters(staging_threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    domains = Counter(thread["sender_domain"] for thread in staging_threads if thread.get("sender_domain"))
    filters = [
        {
            "id": f"allow-domain-{domain.replace('.', '-')}",
            "effect": "allow",
            "field": "sender",
            "operator": "domain_equals",
            "value": domain,
            "enabled": False,
        }
        for domain, _count in domains.most_common(3)
    ]
    filters.append({
        "id": "deny-newsletter-subject",
        "effect": "deny",
        "field": "subject",
        "operator": "contains",
        "value": "newsletter",
        "enabled": True,
    })
    return filters


def _sender_domain(sender: str) -> str:
    address = parseaddr(sender)[1] or sender
    if "@" not in address:
        return ""
    return address.rsplit("@", 1)[1].casefold()


def _source_ref(subject: str, sender: str, received_at: str) -> str:
    digest = hashlib.sha256(f"{subject}\n{sender}\n{received_at}".encode("utf-8")).hexdigest()[:16]
    return f"gmail:{digest}"


def _summarize_text(text: str, limit: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit - 1].rstrip()}..."


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if str(item).strip()]


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _confidence_or_none(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, confidence))


def _json_or_empty_list(value: str) -> list:
    import json

    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _json_or_empty_dict(value: str) -> dict:
    import json

    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
