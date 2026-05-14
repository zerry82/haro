from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable

from app.services.llm import get_client

MODEL_NAME = "gemini-3-flash-preview"
BATCH_SIZE = 10
BODY_SAMPLE_LIMIT = 1200


@dataclass(frozen=True)
class MailStructuringResult:
    structured_by_ref: dict[str, dict[str, Any]]
    warning_count: int


class MailStructuringService:
    def __init__(
        self,
        client_factory: Callable[[], Any] = get_client,
        model_name: str = MODEL_NAME,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        self.client_factory = client_factory
        self.model_name = model_name
        self.batch_size = batch_size

    async def structure_threads(self, threads: list[dict[str, Any]]) -> MailStructuringResult:
        structured_by_ref: dict[str, dict[str, Any]] = {}
        for batch in _batches(threads, self.batch_size):
            batch_result = await self._structure_batch(batch)
            structured_by_ref.update(batch_result)
        warning_count = sum(len(item.get("structure_warnings") or []) for item in structured_by_ref.values())
        return MailStructuringResult(structured_by_ref=structured_by_ref, warning_count=warning_count)

    async def _structure_batch(self, threads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        try:
            text = await asyncio.to_thread(self._generate, _build_prompt(threads))
            parsed = _parse_structuring_response(text)
            return _normalize_response_threads(parsed, threads)
        except Exception as exc:
            return {str(thread.get("source_ref") or ""): _fallback_thread(thread, str(exc)) for thread in threads}

    def _generate(self, prompt: str) -> str:
        response = self.client_factory().models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
        )
        return str(getattr(response, "text", "") or "")


def _build_prompt(threads: list[dict[str, Any]]) -> str:
    payload = [_prompt_thread(thread) for thread in threads]
    return (
        "You structure Gmail thread snapshots for a B2B context library.\n"
        "Return strict JSON only. Do not include markdown.\n"
        "For every input thread, return one item with the same source_ref.\n"
        "Schema: {\"threads\":[{\"source_ref\":\"string\",\"summary\":\"Korean concise summary\","
        "\"category\":\"short Korean category\",\"extracted_actions\":[{\"text\":\"string\","
        "\"owner\":\"string or empty\",\"due_date\":\"ISO date or empty\"}],"
        "\"extracted_due_dates\":[{\"date\":\"ISO date or empty\",\"text\":\"string\"}],"
        "\"structure_warnings\":[\"string\"],\"confidence\":0.0}]}\n"
        "Use only the supplied truncated body sample, attachment summaries, and metadata. "
        "If the body only says to check attachments, use attachment summaries as the main business context. "
        "If uncertain, add a warning and lower confidence.\n"
        f"Input threads:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _prompt_thread(thread: dict[str, Any]) -> dict[str, Any]:
    attachments = thread.get("attachments") if isinstance(thread.get("attachments"), list) else []
    return {
        "source_ref": str(thread.get("source_ref") or ""),
        "subject": str(thread.get("subject") or ""),
        "sender": str(thread.get("sender") or ""),
        "recipients": [str(item) for item in thread.get("recipients") or []],
        "received_at": str(thread.get("received_at") or ""),
        "existing_summary": str(thread.get("summary") or ""),
        "body_sample": _limit_text(thread.get("body") or ""),
        "external_links": _string_list((thread.get("metadata") or {}).get("external_links") if isinstance(thread.get("metadata"), dict) else []),
        "attachments": [_prompt_attachment(attachment) for attachment in attachments],
    }


def _prompt_attachment(attachment: Any) -> dict[str, Any]:
    if not isinstance(attachment, dict):
        return {}
    return {
        "title": str(attachment.get("title") or attachment.get("name") or ""),
        "extension": str(attachment.get("extension") or ""),
        "size_bytes": int(attachment.get("size_bytes") or attachment.get("size") or 0),
        "summary": str(attachment.get("summary") or attachment.get("content_summary") or ""),
        "extract_status": str(attachment.get("extract_status") or ""),
        "key_points": _string_list(attachment.get("key_points") or []),
        "content_profile": _compact_profile(attachment.get("content_profile")),
    }


def _parse_structuring_response(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("LLM response did not include a JSON object")
    parsed = json.loads(cleaned[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")
    return parsed


def _normalize_response_threads(parsed: dict[str, Any], input_threads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_ref = {str(item.get("source_ref") or ""): item for item in parsed.get("threads") or [] if isinstance(item, dict)}
    normalized: dict[str, dict[str, Any]] = {}
    for thread in input_threads:
        source_ref = str(thread.get("source_ref") or "")
        item = by_ref.get(source_ref)
        normalized[source_ref] = _normalize_item(item) if item else _fallback_thread(thread, "LLM response omitted this thread")
    return normalized


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": str(item.get("summary") or "").strip(),
        "category": str(item.get("category") or "").strip(),
        "extracted_actions": _dict_list(item.get("extracted_actions")),
        "extracted_due_dates": _dict_list(item.get("extracted_due_dates")),
        "structure_warnings": _string_list(item.get("structure_warnings") or []),
        "confidence": _confidence(item.get("confidence")),
    }


def _fallback_thread(thread: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "summary": str(thread.get("summary") or thread.get("subject") or "").strip(),
        "category": "",
        "extracted_actions": [],
        "extracted_due_dates": [],
        "structure_warnings": [f"LLM 구조화 fallback: {reason}"],
        "confidence": 0.0,
    }


def _batches(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(item) for item in value if str(item).strip()]


def _confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _limit_text(value: Any, limit: int = BODY_SAMPLE_LIMIT) -> str:
    cleaned = " ".join(str(value or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit - 1].rstrip()}..."


def _compact_profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "kind",
        "text_preview",
        "columns",
        "row_count",
        "row_count_sampled",
        "sheets",
        "page_count",
        "image_description",
        "visible_text",
        "summary_status",
    }
    return {key: value.get(key) for key in allowed if key in value}
