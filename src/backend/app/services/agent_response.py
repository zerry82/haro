from __future__ import annotations

"""에이전트 응답 텍스트와 도구 호출 보조 함수."""

import json
import re
from dataclasses import dataclass
from typing import Any


TOOL_CALL_PATTERN = r"```tool_call\s*\n?(.*?)\n?```"


@dataclass(frozen=True)
class ToolCallParseResult:
    has_block: bool
    tool_call: dict | None = None
    error: str | None = None
    raw_block: str | None = None


def parse_tool_call_result(text: str) -> ToolCallParseResult:
    match = re.search(TOOL_CALL_PATTERN, text, re.DOTALL)
    if not match:
        return ToolCallParseResult(has_block=False)

    raw_block = match.group(1).strip()
    try:
        parsed = json.loads(raw_block)
    except json.JSONDecodeError as exc:
        return ToolCallParseResult(
            has_block=True,
            error=f"{exc.msg} at line {exc.lineno} column {exc.colno} (char {exc.pos})",
            raw_block=raw_block,
        )

    if not isinstance(parsed, dict):
        return ToolCallParseResult(
            has_block=True,
            error="tool_call JSON must be an object",
            raw_block=raw_block,
        )

    return ToolCallParseResult(has_block=True, tool_call=parsed, raw_block=raw_block)


def parse_tool_call(text: str) -> dict | None:
    return parse_tool_call_result(text).tool_call


def extract_text_without_tool_call(text: str) -> str:
    return re.sub(TOOL_CALL_PATTERN, "", text, flags=re.DOTALL).strip()


def blocked_tool_result(tool_name: str, selected_tools: list[str]) -> str:
    allowed = ", ".join(selected_tools) or "없음"
    return f"도구 사용 차단: {tool_name}는 이번 intent turn에 선택되지 않았습니다. 선택된 도구: {allowed}"


def blocked_tool_message(tool_name: str, selected_tools: list[str]) -> str:
    allowed = ", ".join(f"`{name}`" for name in selected_tools) or "없음"
    if tool_name in {
        "file_create",
        "file_write",
        "file_edit",
        "file_append",
        "file_replace_range",
        "file_delete",
        "file_move",
        "dir_create",
        "dir_delete",
        "file_export",
    }:
        action = "파일 또는 폴더 변경"
    elif tool_name == "file_read":
        action = "파일 읽기"
    else:
        action = "도구 실행"
    return (
        f"이번 턴에서는 `{tool_name}` 도구가 선택되지 않아 {action}을 실행하지 않았습니다. "
        f"선택된 도구는 {allowed}입니다. 앞선 답변에서 파일 생성이나 수정이 언급되었더라도 "
        "실제로 수행된 변경은 없습니다."
    )


def routing_context_instruction(route: Any) -> str:
    return working_context_instruction(route)


def working_context_instruction(route: Any) -> str:
    if not route.routing_context:
        return ""
    context = executor_routing_context(route.routing_context)
    return (
        "\n\n[현재 작업 맥락]\n"
        "아래 JSON은 현재 턴의 작업 맥락입니다. 라우터가 작업 의미를 확정한 것이 아니며, "
        "대화 전체, 열린 파일, 최근 산출물, 도구 결과 후보를 종합해 executor가 판단해야 합니다.\n"
        "- active file과 latest artifact가 다르면 active file을 우선하고 둘을 구분해 설명하세요.\n"
        "- 낮은 위험의 read-only 요청은 확신이 충분하면 바로 진행하세요.\n"
        "- 파일 변경/삭제/이동에서 대상이나 작업 단위가 모호하면 후보와 이유를 들어 확인 질문을 하세요.\n"
        "- 같은 검색을 반복하지 말고, source가 없으면 확인한 위치와 누락 정보를 요약해 경로/재업로드를 요청하세요.\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2, default=str)}"
    )


def executor_routing_context(context: dict) -> dict:
    gate_context = context.get("gate_context") or {}
    compact_gate = {
        key: gate_context.get(key)
        for key in [
            "decision",
            "source",
            "confidence",
            "artifact_path",
            "artifact_kind",
            "artifact_url",
            "artifact_action",
            "intent_turn_id",
        ]
        if gate_context.get(key) is not None
    }
    if gate_context.get("reason"):
        compact_gate["reason"] = compact_text(str(gate_context["reason"]), 360)

    compact: dict = {
        "current_user_message": context.get("current_user_message"),
        "routing_text": context.get("routing_text"),
        "chat_workspace": context.get("chat_workspace"),
        "gate_context": compact_gate or None,
        "execution_policy": compact_execution_policy(context.get("execution_policy")),
        "is_clarification_answer": context.get("is_clarification_answer"),
        "previous_intent": context.get("previous_intent"),
        "clarification_question": context.get("clarification_question"),
        "latest_artifact": context.get("latest_artifact"),
        "latest_preview": context.get("latest_preview"),
        "file_discovery_context": compact_file_discovery_context(context.get("file_discovery_context")),
    }
    return {key: value for key, value in compact.items() if value not in (None, [], {})}


def compact_execution_policy(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    return {
        key: value.get(key)
        for key in [
            "profile",
            "confidence",
            "risk_level",
            "reason",
            "context_confidence",
            "target_confidence",
            "source_confidence",
            "operation_confidence",
        ]
        if value.get(key) is not None
    }


def compact_file_discovery_context(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    candidates = value.get("candidates") if isinstance(value.get("candidates"), list) else []
    compact_candidates = []
    for candidate in candidates[:5]:
        if not isinstance(candidate, dict):
            continue
        compact_candidates.append({
            key: candidate.get(key)
            for key in [
                "alias_path",
                "path",
                "role",
                "confidence",
                "reasons",
                "recommended_action",
                "source",
                "message_id",
                "message_role",
                "content_preview",
            ]
            if candidate.get(key) not in (None, [], {})
        })
    context = {
        "requires_source_content": value.get("requires_source_content"),
        "source_content_missing": value.get("source_content_missing"),
        "candidates": compact_candidates,
        "search_plan": value.get("search_plan"),
        "missing_info": value.get("missing_info"),
        "recommended_user_question": value.get("recommended_user_question"),
        "open_file_context": value.get("open_file_context"),
    }
    return {key: item for key, item in context.items() if item not in (None, [], {})}


def compact_text(text: str, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."
