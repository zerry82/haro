from __future__ import annotations

"""Turn-local file discovery context for intent routing and execution."""

import os
from dataclasses import dataclass, field
from typing import Any

from app.models.chat_session import ChatSession
from app.services.chat_workspace_files import load_json_file
from app.services.harness import normalize_workspace_path
from app.services.workspace_aliases import alias_path_for_canonical_path, resolve_workspace_alias_path
from app.services.workspace_file_db import (
    list_workspace_directory_page,
    search_workspace_files,
)


MAX_CANDIDATES = 8
MAX_SELECTION_PREVIEW_CHARS = 2000
MAX_CONVERSATION_SOURCE_PREVIEW_CHARS = 1200

LINKED_FILES_FALLBACK = {
    "inputs": [],
    "derived": [],
    "outputs": [],
    "exports": [],
    "previews": [],
}

SOURCE_FILE_SIGNALS = (
    "이미 파일",
    "파일로 추가",
    "파일로 올",
    "파일로 넣",
    "기존에 작성",
    "전에 작성",
    "아까 작성",
    "업로드",
    "첨부",
    "추가했",
)

CONVERSATION_SOURCE_SIGNALS = (
    "기존에 작성",
    "전에 작성",
    "아까 작성",
    "방금 작성",
    "위에 작성",
    "이미 작성",
)

STATUS_MESSAGE_SIGNALS = (
    "찾아보겠습니다",
    "확인해 보겠습니다",
    "검색해 보겠습니다",
    "살펴보겠습니다",
    "진행하겠습니다",
    "도구 실행 결과",
)

CURRENT_FILE_SIGNALS = (
    "이 파일",
    "현재 파일",
    "열어둔 파일",
    "지금 보고",
    "보고 있는 파일",
)

TARGET_ARTIFACT_SIGNALS = (
    "html",
    "대시보드",
    "브리핑",
    "리포트",
    "문서",
)

STOPWORDS = {
    "에서",
    "현재",
    "아래",
    "내용",
    "추가",
    "파일",
    "이미",
    "해줘",
    "그리고",
    "the",
    "and",
    "with",
}


@dataclass
class FileDiscoveryCandidate:
    path: str
    role: str
    confidence: float
    reasons: list[str] = field(default_factory=list)
    recommended_action: str = "inspect"
    kind: str | None = None
    language: str | None = None
    source: str | None = None
    message_id: str | None = None
    message_role: str | None = None
    content_preview: str | None = None


def sanitize_open_file_context(payload: dict[str, Any] | None, user_id: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    active_path = _resolve_path(payload.get("active_file_path"), user_id)
    opened_paths = []
    for item in _as_list(payload.get("opened_file_paths")):
        resolved = _resolve_path(item, user_id)
        if resolved and resolved not in opened_paths:
            opened_paths.append(resolved)
    if active_path and active_path not in opened_paths:
        opened_paths.insert(0, active_path)

    selection = _sanitize_selection(payload.get("selection"))
    context = {
        "active_file_path": active_path,
        "opened_file_paths": opened_paths[:5],
        "language": _string_or_none(payload.get("language")),
        "active_viewer_tab": _string_or_none(payload.get("active_viewer_tab")),
        "dirty": bool(payload.get("dirty")),
        "selection": selection,
    }
    return {key: value for key, value in context.items() if value not in (None, [], {})}


def build_file_discovery_context(
    *,
    workspace: str | None,
    user_id: str | None,
    chat_session: ChatSession,
    current_message: str,
    routing_text: str,
    open_file_context: dict[str, Any] | None = None,
    latest_artifact: dict[str, Any] | None = None,
    latest_preview: dict[str, Any] | None = None,
    recent_messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not workspace or not user_id:
        return None

    candidates: dict[tuple[str, str], FileDiscoveryCandidate] = {}
    text = f"{routing_text}\n{current_message}".lower()
    requires_source = _expects_source_content(text)

    _add_open_file_candidates(candidates, open_file_context, user_id, text)
    _add_latest_artifact_candidate(candidates, latest_artifact, text)
    _add_conversation_source_candidates(candidates, recent_messages, current_message, text)
    _add_linked_file_candidates(candidates, workspace, chat_session)
    _add_artifacts_file_candidates(candidates, workspace, chat_session)
    _add_chat_folder_candidates(candidates, workspace, chat_session, user_id)
    _add_search_candidates(candidates, workspace, user_id, routing_text, latest_artifact)

    ordered = sorted(candidates.values(), key=lambda item: item.confidence, reverse=True)[:MAX_CANDIDATES]
    if not ordered and not open_file_context and not latest_artifact and not requires_source:
        return None

    source_candidates = [item for item in ordered if item.role == "source_content"]
    source_missing = bool(requires_source and not source_candidates)
    result = {
        "requires_source_content": requires_source,
        "source_content_missing": source_missing,
        "candidates": [_candidate_to_dict(item, user_id) for item in ordered],
        "search_plan": _search_plan(requires_source, bool(ordered), source_missing),
    }
    if open_file_context:
        result["open_file_context"] = _compact_open_file_context(open_file_context, user_id)
    if latest_preview:
        result["latest_preview"] = latest_preview
    if source_missing:
        result["missing_info"] = ["추가할 원문 파일 경로 또는 재업로드"]
        result["recommended_user_question"] = (
            "추가하신 원문 파일을 현재 확인 가능한 위치에서 찾지 못했습니다. "
            "파일 경로를 알려주시거나 다시 업로드해 주세요."
        )
    return result


def _add_open_file_candidates(
    candidates: dict[tuple[str, str], FileDiscoveryCandidate],
    context: dict[str, Any] | None,
    user_id: str,
    text: str,
) -> None:
    if not context:
        return
    active = _string_or_none(context.get("active_file_path"))
    opened = [_string_or_none(item) for item in _as_list(context.get("opened_file_paths"))]
    opened = [item for item in opened if item]
    active_is_current_ref = any(signal in text for signal in CURRENT_FILE_SIGNALS)
    for index, path in enumerate(opened):
        role = "context_file"
        confidence = 0.66
        reasons = ["Haro UI에서 열려 있는 파일입니다."]
        if path == active:
            confidence = 0.92 if active_is_current_ref else 0.78
            reasons = ["Haro UI의 현재 활성 파일입니다."]
            if _looks_like_target_artifact(path, text):
                role = "target_artifact"
        if context.get("dirty") and path == active:
            reasons.append("저장되지 않은 변경사항이 있어 디스크 내용과 다를 수 있습니다.")
        if context.get("selection") and path == active:
            reasons.append("사용자가 선택한 범위가 포함되어 있습니다.")
        _upsert_candidate(
            candidates,
            FileDiscoveryCandidate(
                path=path,
                role=role,
                confidence=confidence - (0.04 * index),
                reasons=reasons,
                recommended_action="read_selection_or_file" if path == active else "inspect_if_needed",
                kind="open_file",
                language=_string_or_none(context.get("language")) if path == active else None,
                source="open_file_context",
            ),
        )


def _add_latest_artifact_candidate(
    candidates: dict[tuple[str, str], FileDiscoveryCandidate],
    latest_artifact: dict[str, Any] | None,
    text: str,
) -> None:
    path = _string_or_none((latest_artifact or {}).get("path"))
    if not path:
        return
    confidence = 0.9 if _looks_like_target_artifact(path, text) else 0.82
    _upsert_candidate(
        candidates,
        FileDiscoveryCandidate(
            path=normalize_workspace_path(path),
            role="target_artifact",
            confidence=confidence,
            reasons=["최근 채팅 산출물입니다."],
            recommended_action="read_or_search_target",
            kind=_string_or_none((latest_artifact or {}).get("kind")),
            source="latest_artifact",
        ),
    )


def _add_conversation_source_candidates(
    candidates: dict[tuple[str, str], FileDiscoveryCandidate],
    recent_messages: list[dict[str, Any]] | None,
    current_message: str,
    text: str,
) -> None:
    if not recent_messages or not _expects_conversation_source(text):
        return

    current_compact = _compact_text(current_message)
    for message in reversed(recent_messages):
        content = _string_or_none(message.get("content") if isinstance(message, dict) else None)
        if not content or _compact_text(content) == current_compact:
            continue
        if not _looks_like_source_message(content):
            continue

        message_id = _string_or_none(message.get("id")) or "unknown"
        role = _string_or_none(message.get("role"))
        _upsert_candidate(
            candidates,
            FileDiscoveryCandidate(
                path=f"conversation://messages/{message_id}",
                role="source_content",
                confidence=0.82 if role == "user" else 0.72,
                reasons=["최근 대화에 사용자가 말한 기존 작성 내용 후보가 있습니다."],
                recommended_action="use_conversation_preview",
                kind="conversation_message",
                source="recent_messages",
                message_id=message_id,
                message_role=role,
                content_preview=_truncate(content, MAX_CONVERSATION_SOURCE_PREVIEW_CHARS),
            ),
        )
        return


def _add_linked_file_candidates(
    candidates: dict[tuple[str, str], FileDiscoveryCandidate],
    workspace: str,
    chat_session: ChatSession,
) -> None:
    if not chat_session.folder_path:
        return
    linked = load_json_file(workspace, chat_session.folder_path, "linked-files.json", LINKED_FILES_FALLBACK)
    for item in _as_list(linked.get("inputs")):
        path = _path_from_entry(item, "path")
        if path:
            _upsert_candidate(
                candidates,
                FileDiscoveryCandidate(
                    path=path,
                    role="source_content",
                    confidence=0.88,
                    reasons=["현재 채팅에 연결된 입력 파일입니다."],
                    recommended_action="read_source",
                    kind="linked_input",
                    source="linked-files.json",
                ),
            )
    for key, role, confidence, reason in [
        ("outputs", "target_artifact", 0.84, "현재 채팅에 연결된 출력 파일입니다."),
        ("derived", "context_file", 0.74, "현재 채팅에서 파생된 파일입니다."),
        ("exports", "target_artifact", 0.82, "현재 채팅에서 export된 파일입니다."),
    ]:
        for item in _as_list(linked.get(key)):
            path = _path_from_entry(item, "path", "target_path", "source_path")
            if path:
                _upsert_candidate(
                    candidates,
                    FileDiscoveryCandidate(
                        path=path,
                        role=role,
                        confidence=confidence,
                        reasons=[reason],
                        recommended_action="inspect",
                        kind=f"linked_{key}",
                        source="linked-files.json",
                    ),
                )


def _add_artifacts_file_candidates(
    candidates: dict[tuple[str, str], FileDiscoveryCandidate],
    workspace: str,
    chat_session: ChatSession,
) -> None:
    if not chat_session.folder_path:
        return
    artifacts = load_json_file(workspace, chat_session.folder_path, "artifacts.json", {})
    for path in _extract_paths(artifacts):
        _upsert_candidate(
            candidates,
            FileDiscoveryCandidate(
                path=path,
                role="target_artifact",
                confidence=0.8,
                reasons=["현재 채팅 artifacts metadata에 기록된 파일입니다."],
                recommended_action="inspect",
                kind="artifact",
                source="artifacts.json",
            ),
        )


def _add_chat_folder_candidates(
    candidates: dict[tuple[str, str], FileDiscoveryCandidate],
    workspace: str,
    chat_session: ChatSession,
    user_id: str,
) -> None:
    if not chat_session.folder_path:
        return
    for child, role, confidence, reason in [
        ("inputs", "source_content", 0.78, "현재 채팅 inputs 폴더의 파일입니다."),
        ("outputs", "target_artifact", 0.76, "현재 채팅 outputs 폴더의 파일입니다."),
        ("working", "context_file", 0.68, "현재 채팅 working 폴더의 파일입니다."),
    ]:
        folder = normalize_workspace_path(f"{chat_session.folder_path}/{child}")
        try:
            page = list_workspace_directory_page(workspace, folder, limit=5, include_hidden=False, user_id=user_id)
        except Exception:
            continue
        for item in page.get("items") or []:
            if item.get("type") != "file":
                continue
            path = normalize_workspace_path(f"{folder}/{item.get('name')}")
            _upsert_candidate(
                candidates,
                FileDiscoveryCandidate(
                    path=path,
                    role=role,
                    confidence=confidence,
                    reasons=[reason],
                    recommended_action="read_source" if role == "source_content" else "inspect",
                    kind="chat_workspace_file",
                    source=f"chat_{child}",
                ),
            )


def _add_search_candidates(
    candidates: dict[tuple[str, str], FileDiscoveryCandidate],
    workspace: str,
    user_id: str,
    routing_text: str,
    latest_artifact: dict[str, Any] | None,
) -> None:
    queries = _search_queries(routing_text, latest_artifact)
    for query in queries[:2]:
        try:
            rows = search_workspace_files(
                workspace,
                query,
                item_type="file",
                limit=5,
                include_hidden=False,
                user_id=user_id,
            )
        except Exception:
            continue
        for row in rows:
            path = _string_or_none(row.get("path"))
            if not path:
                continue
            _upsert_candidate(
                candidates,
                FileDiscoveryCandidate(
                    path=normalize_workspace_path(path),
                    role="context_file",
                    confidence=0.62,
                    reasons=[f"워크스페이스 인덱스에서 `{query}` 검색으로 발견되었습니다."],
                    recommended_action="inspect_if_needed",
                    kind=_string_or_none(row.get("item_type")),
                    language=_string_or_none(row.get("language")),
                    source="bounded_workspace_search",
                ),
            )


def _upsert_candidate(
    candidates: dict[tuple[str, str], FileDiscoveryCandidate],
    candidate: FileDiscoveryCandidate,
) -> None:
    candidate.path = _normalize_candidate_path(candidate.path)
    key = (candidate.path, candidate.role)
    existing = candidates.get(key)
    if not existing:
        candidates[key] = candidate
        return
    existing.confidence = max(existing.confidence, candidate.confidence)
    existing.reasons = _dedupe([*existing.reasons, *candidate.reasons])
    existing.recommended_action = existing.recommended_action or candidate.recommended_action
    existing.kind = existing.kind or candidate.kind
    existing.language = existing.language or candidate.language
    existing.source = existing.source or candidate.source
    existing.message_id = existing.message_id or candidate.message_id
    existing.message_role = existing.message_role or candidate.message_role
    existing.content_preview = existing.content_preview or candidate.content_preview


def _candidate_to_dict(candidate: FileDiscoveryCandidate, user_id: str) -> dict[str, Any]:
    payload = {
        "path": candidate.path,
        "alias_path": _alias_path_for_candidate(candidate.path, user_id),
        "role": candidate.role,
        "confidence": round(candidate.confidence, 2),
        "reasons": candidate.reasons[:4],
        "recommended_action": candidate.recommended_action,
        "kind": candidate.kind,
        "language": candidate.language,
        "source": candidate.source,
        "message_id": candidate.message_id,
        "message_role": candidate.message_role,
        "content_preview": candidate.content_preview,
    }
    return {key: value for key, value in payload.items() if value not in (None, [], {})}


def _compact_open_file_context(context: dict[str, Any], user_id: str) -> dict[str, Any]:
    active = _string_or_none(context.get("active_file_path"))
    selection = context.get("selection") if isinstance(context.get("selection"), dict) else None
    payload = {
        "active_file_path": active,
        "active_alias_path": alias_path_for_canonical_path(active, user_id) if active else None,
        "opened_file_paths": _as_list(context.get("opened_file_paths"))[:5],
        "language": _string_or_none(context.get("language")),
        "active_viewer_tab": _string_or_none(context.get("active_viewer_tab")),
        "dirty": bool(context.get("dirty")),
        "selection": selection,
    }
    return {key: value for key, value in payload.items() if value not in (None, [], {})}


def _search_plan(requires_source: bool, has_candidates: bool, source_missing: bool) -> list[str]:
    if source_missing:
        return [
            "Use structured candidates first: open file, recent conversation, linked inputs, artifacts, chat inputs.",
            "Treat latest artifact/output as target, not as the missing source content.",
            "Stop broad repeated search and ask the user for the source file path or upload.",
        ]
    if requires_source:
        return [
            "Read the highest confidence source_content candidate.",
            "Use target_artifact candidates only as the destination or constraint context.",
        ]
    if has_candidates:
        return ["Inspect the highest confidence candidate before broad file search."]
    return ["No deterministic file candidate was found; use bounded file_search if the request needs files."]


def _sanitize_selection(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    start_line = _int_or_none(value.get("start_line"))
    end_line = _int_or_none(value.get("end_line"))
    text_preview = _string_or_none(value.get("text_preview"))
    if text_preview:
        text_preview = text_preview[:MAX_SELECTION_PREVIEW_CHARS]
    payload = {
        "start_line": start_line,
        "end_line": end_line,
        "text_preview": text_preview,
    }
    return {key: item for key, item in payload.items() if item not in (None, "")} or None


def _resolve_path(value: Any, user_id: str) -> str | None:
    text = _string_or_none(value)
    if not text:
        return None
    try:
        return resolve_workspace_alias_path(text, user_id)
    except Exception:
        return normalize_workspace_path(text)


def _normalize_candidate_path(path: str) -> str:
    if path.startswith("conversation://"):
        return path
    return normalize_workspace_path(path)


def _alias_path_for_candidate(path: str, user_id: str) -> str:
    if path.startswith("conversation://messages/"):
        message_id = path.rsplit("/", 1)[-1]
        return f"최근 대화 메시지/{message_id}"
    return alias_path_for_canonical_path(path, user_id)


def _path_from_entry(entry: Any, *keys: str) -> str | None:
    if not isinstance(entry, dict):
        return None
    for key in keys:
        path = _string_or_none(entry.get(key))
        if path:
            return normalize_workspace_path(path)
    return None


def _extract_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"path", "target_path", "source_path"}:
                path = _string_or_none(item)
                if path:
                    paths.append(normalize_workspace_path(path))
            else:
                paths.extend(_extract_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.extend(_extract_paths(item))
    return _dedupe(paths)


def _search_queries(routing_text: str, latest_artifact: dict[str, Any] | None) -> list[str]:
    tokens = []
    for raw in (routing_text or "").replace("_", " ").replace("-", " ").replace(".", " ").split():
        token = raw.strip("`'\".,:;!?()[]{}").lower()
        if len(token) >= 2 and token not in STOPWORDS:
            tokens.append(token)
    artifact_path = _string_or_none((latest_artifact or {}).get("path"))
    if artifact_path:
        stem = os.path.splitext(os.path.basename(artifact_path))[0]
        tokens.extend(part for part in stem.replace("_", " ").split() if len(part) >= 2)
    deduped = _dedupe(tokens)
    if not deduped:
        return []
    queries = []
    if len(deduped) >= 2:
        queries.append(" ".join(deduped[:3]))
    queries.extend(deduped[:2])
    return _dedupe(queries)


def _expects_source_content(text: str) -> bool:
    return any(signal in text for signal in SOURCE_FILE_SIGNALS)


def _expects_conversation_source(text: str) -> bool:
    return any(signal in text for signal in CONVERSATION_SOURCE_SIGNALS)


def _looks_like_source_message(content: str) -> bool:
    compact = _compact_text(content)
    if len(compact) < 40:
        return False
    if "```tool_call" in compact:
        return False
    return not any(signal in compact for signal in STATUS_MESSAGE_SIGNALS)


def _looks_like_target_artifact(path: str, text: str) -> bool:
    lowered_path = path.lower()
    extension = os.path.splitext(lowered_path)[1]
    if extension in {".html", ".htm", ".md", ".pdf"} and any(signal in text for signal in TARGET_ARTIFACT_SIGNALS):
        return True
    return any(signal in lowered_path for signal in ("dashboard", "대시보드", "브리핑", "report", "리포트"))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _compact_text(text: str) -> str:
    return " ".join((text or "").split())


def _truncate(text: str, limit: int) -> str:
    compact = _compact_text(text)
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _dedupe(values: list[Any]) -> list[Any]:
    result = []
    seen = set()
    for value in values:
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
