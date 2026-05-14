from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mail import MailAnalysisRun, MailThreadStaging
from app.services.mail_vector_index import (
    MailVectorSearchStore,
    MailVectorSearchUnavailable,
    merge_vector_and_text_results,
)


class MailSearchRunNotFoundError(RuntimeError):
    pass


class MailSearchRunNotReadyError(RuntimeError):
    pass


@dataclass(frozen=True)
class MailSearchResult:
    run: MailAnalysisRun
    query: str
    items: list[dict[str, Any]]
    retrieval: dict[str, Any]


async def search_mail_analysis(
    db: AsyncSession,
    *,
    project_id: str,
    user_id: str,
    run_id: str | None,
    query: str,
    limit: int = 10,
    workspace_path: str | None = None,
) -> MailSearchResult:
    run = await _resolve_run(db, project_id=project_id, user_id=user_id, run_id=run_id)
    threads = _managed_threads(await _threads_for_run(db, run, project_id=project_id, user_id=user_id))
    text_items = rank_mail_threads(threads, query=query, limit=max(limit, 50))
    terms = _query_terms(query)
    if not terms:
        items = text_items[: max(1, min(limit, 50))]
        retrieval = {"mode": "text_recent", "vector": {"enabled": False, "reason": "empty_effective_query"}}
    else:
        if not workspace_path:
            raise MailVectorSearchUnavailable("workspace_path is required for mail vector search")
        vector_hits = MailVectorSearchStore(workspace_path).search(
            run_id=run.id,
            threads=threads,
            query=query,
            limit=max(limit, 20),
        )
        items = (
            merge_vector_and_text_results(
                threads,
                vector_hits=vector_hits,
                text_items=text_items,
                limit=limit,
            )
            if vector_hits
            else []
        )
        retrieval = {
            "mode": "hybrid_vector",
            "vector": {
                "enabled": True,
                "hit_count": len(vector_hits),
            },
        }
    for item in items:
        item.setdefault("retrieval", {"mode": retrieval["mode"]})
    return MailSearchResult(
        run=run,
        query=query,
        items=items,
        retrieval=retrieval,
    )


def rank_mail_threads(
    threads: list[MailThreadStaging],
    *,
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for thread in threads:
        item = _thread_search_item(thread)
        score, matched_fields, evidence = _score_item(item, terms, query)
        if not terms:
            score = 1
            matched_fields = []
            evidence = []
        if score <= 0:
            continue
        item["score"] = score
        item["matched_fields"] = matched_fields
        item["evidence"] = evidence[:5]
        scored.append((score, str(item.get("received_at") or ""), item))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [item for _score, _received_at, item in scored[: max(1, min(limit, 50))]]


def _managed_threads(threads: list[MailThreadStaging]) -> list[MailThreadStaging]:
    rows: list[MailThreadStaging] = []
    for thread in threads:
        metadata = _loads(thread.metadata_json, {})
        if metadata.get("management_decision") == "excluded":
            continue
        rows.append(thread)
    return rows


async def _resolve_run(
    db: AsyncSession,
    *,
    project_id: str,
    user_id: str,
    run_id: str | None,
) -> MailAnalysisRun:
    if not run_id or run_id == "latest":
        result = await db.execute(
            select(MailAnalysisRun)
            .where(
                MailAnalysisRun.project_id == project_id,
                MailAnalysisRun.user_id == user_id,
                MailAnalysisRun.status == "completed",
            )
            .order_by(desc(MailAnalysisRun.created_at))
            .limit(1)
        )
    else:
        result = await db.execute(
            select(MailAnalysisRun).where(
                MailAnalysisRun.id == run_id,
                MailAnalysisRun.project_id == project_id,
                MailAnalysisRun.user_id == user_id,
            )
        )
    run = result.scalar_one_or_none()
    if not run:
        raise MailSearchRunNotFoundError("Gmail 분석 결과가 없습니다. 먼저 메일 관리에서 최근 분석을 실행해 주세요.")
    if run.status != "completed":
        raise MailSearchRunNotReadyError(f"Gmail 분석이 아직 완료되지 않았습니다. 현재 상태: {run.status}")
    return run


async def _threads_for_run(
    db: AsyncSession,
    run: MailAnalysisRun,
    *,
    project_id: str,
    user_id: str,
) -> list[MailThreadStaging]:
    current = await _direct_threads_for_run(db, run, project_id=project_id, user_id=user_id)
    if not run.source_run_id:
        return current
    result = await db.execute(
        select(MailAnalysisRun).where(
            MailAnalysisRun.id == run.source_run_id,
            MailAnalysisRun.project_id == project_id,
            MailAnalysisRun.user_id == user_id,
        )
    )
    source_run = result.scalar_one_or_none()
    if not source_run:
        return current
    return _merge_thread_rows(await _threads_for_run(db, source_run, project_id=project_id, user_id=user_id), current)


async def _direct_threads_for_run(
    db: AsyncSession,
    run: MailAnalysisRun,
    *,
    project_id: str,
    user_id: str,
) -> list[MailThreadStaging]:
    result = await db.execute(
        select(MailThreadStaging)
        .where(
            MailThreadStaging.run_id == run.id,
            MailThreadStaging.project_id == project_id,
            MailThreadStaging.user_id == user_id,
        )
        .order_by(MailThreadStaging.received_at.desc())
    )
    return list(result.scalars().all())


def _merge_thread_rows(base: list[MailThreadStaging], new: list[MailThreadStaging]) -> list[MailThreadStaging]:
    by_ref: dict[str, MailThreadStaging] = {}
    for thread in [*base, *new]:
        if thread.source_ref:
            by_ref[thread.source_ref] = thread
    rows = list(by_ref.values())
    rows.sort(key=lambda item: item.received_at, reverse=True)
    return rows


def _thread_search_item(thread: MailThreadStaging) -> dict[str, Any]:
    recipients = _loads(thread.recipients_json, [])
    attachments = _loads(thread.attachments_json, [])
    metadata = _loads(thread.metadata_json, {})
    extracted_actions = _list(metadata.get("extracted_actions"))
    extracted_due_dates = _list(metadata.get("extracted_due_dates"))
    structure_warnings = [str(item) for item in _list(metadata.get("structure_warnings"))]
    return {
        "id": thread.id,
        "thread_id": thread.id,
        "subject": thread.subject,
        "sender": thread.sender,
        "recipients": recipients,
        "received_at": thread.received_at,
        "summary": thread.summary,
        "category": thread.category,
        "attachments": attachments,
        "inclusion_decision": thread.inclusion_decision,
        "metadata": {
            "extracted_actions": extracted_actions,
            "extracted_due_dates": extracted_due_dates,
            "structure_warnings": structure_warnings,
            "confidence": metadata.get("confidence"),
        },
    }


def _score_item(item: dict[str, Any], terms: list[str], raw_query: str) -> tuple[int, list[str], list[dict[str, str]]]:
    field_values = _searchable_fields(item)
    score = 0
    matched_fields: list[str] = []
    evidence: list[dict[str, str]] = []
    phrase = _normalize_text(raw_query)
    for field, value in field_values.items():
        normalized_value = _normalize_text(value)
        if not normalized_value:
            continue
        field_score = 0
        if phrase and phrase in normalized_value:
            field_score += 8
        for term in terms:
            if term and term in normalized_value:
                field_score += _field_weight(field)
        if field_score <= 0:
            continue
        score += field_score
        matched_fields.append(field)
        evidence.append({"field": field, "snippet": _snippet(value, terms or [phrase])})
    return score, matched_fields, evidence


def _searchable_fields(item: dict[str, Any]) -> dict[str, str]:
    attachments = item.get("attachments") if isinstance(item.get("attachments"), list) else []
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return {
        "subject": str(item.get("subject") or ""),
        "sender": str(item.get("sender") or ""),
        "recipients": " ".join(str(value) for value in item.get("recipients") or []),
        "summary": str(item.get("summary") or ""),
        "category": str(item.get("category") or ""),
        "attachments": " ".join(
            _attachment_search_text(attachment)
            for attachment in attachments
        ),
        "extracted_actions": _json_text(metadata.get("extracted_actions")),
        "extracted_due_dates": _json_text(metadata.get("extracted_due_dates")),
        "structure_warnings": _json_text(metadata.get("structure_warnings")),
        "external_links": _json_text(metadata.get("external_links")),
    }


def _attachment_search_text(attachment: Any) -> str:
    if not isinstance(attachment, dict):
        return ""
    profile = attachment.get("content_profile") if isinstance(attachment.get("content_profile"), dict) else {}
    return " ".join(
        str(value)
        for value in (
            attachment.get("title"),
            attachment.get("extension"),
            attachment.get("summary"),
            " ".join(str(item) for item in attachment.get("key_points") or []),
            profile.get("text_preview"),
            profile.get("image_description"),
            profile.get("visible_text"),
            json.dumps(profile.get("columns") or [], ensure_ascii=False),
            json.dumps(profile.get("sheets") or [], ensure_ascii=False),
        )
        if str(value or "").strip()
    )


def _query_terms(query: str) -> list[str]:
    raw_tokens = re.findall(r"[\w가-힣@._+-]+", _normalize_text(query))
    terms: list[str] = []
    for token in raw_tokens:
        variants = [token, _strip_korean_suffix(token)]
        for variant in variants:
            if len(variant) < 2 or variant in _STOPWORDS:
                continue
            if variant not in terms:
                terms.append(variant)
            for alias in _ALIASES.get(variant, []):
                if alias not in terms:
                    terms.append(alias)
    return terms


def _strip_korean_suffix(token: str) -> str:
    suffixes = (
        "에게서",
        "으로부터",
        "로부터",
        "에서",
        "에게",
        "한테",
        "으로",
        "로",
        "부터",
        "까지",
        "들과",
        "들은",
        "들을",
        "들의",
        "들",
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "의",
        "에",
        "도",
        "만",
        "와",
        "과",
    )
    for suffix in suffixes:
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            return token[: -len(suffix)]
    return token


def _field_weight(field: str) -> int:
    return {
        "sender": 6,
        "subject": 5,
        "category": 4,
        "summary": 3,
        "attachments": 3,
        "recipients": 2,
        "extracted_actions": 3,
        "extracted_due_dates": 3,
        "structure_warnings": 2,
    }.get(field, 1)


def _snippet(value: str, terms: list[str], limit: int = 180) -> str:
    compact = " ".join(str(value or "").split())
    if len(compact) <= limit:
        return compact
    normalized = _normalize_text(compact)
    first_index = -1
    for term in terms:
        if not term:
            continue
        index = normalized.find(term)
        if index >= 0 and (first_index < 0 or index < first_index):
            first_index = index
    if first_index < 0:
        return f"{compact[:limit].rstrip()}..."
    start = max(0, first_index - 50)
    end = min(len(compact), start + limit)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end].rstrip()}{suffix}"


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def _json_text(value: Any) -> str:
    if value in (None, [], {}):
        return ""
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: str, default: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


_STOPWORDS = {
    "gmail",
    "email",
    "메일",
    "메일들",
    "이메일",
    "지메일",
    "온",
    "보낸",
    "받은",
    "요약",
    "요약해줘",
    "정리",
    "정리해줘",
    "찾아",
    "찾아줘",
    "검색",
    "검색해줘",
    "알려줘",
    "관련",
    "최근",
    "thread",
    "threads",
    "스레드",
}

_ALIASES = {
    "카카오": ["kakao"],
    "네이버": ["naver"],
    "구글": ["google"],
    "마이크로소프트": ["microsoft"],
    "링크드인": ["linkedin"],
}
