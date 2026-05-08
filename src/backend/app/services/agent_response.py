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
    if tool_name in {"file_create", "file_write", "file_delete", "dir_create", "file_export"}:
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
    if not route.routing_context:
        return ""
    context = executor_routing_context(route.routing_context)
    return (
        "\n\n[현재 턴 라우팅 맥락]\n"
        "아래 JSON은 게이트와 라우터가 판단한 현재 턴의 핵심 맥락입니다. "
        "답변이나 도구 호출이 필요하면 이 정보를 근거로 사용하세요.\n"
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
        "is_clarification_answer": context.get("is_clarification_answer"),
        "previous_intent": context.get("previous_intent"),
        "clarification_question": context.get("clarification_question"),
        "latest_artifact": context.get("latest_artifact"),
        "latest_preview": context.get("latest_preview"),
    }
    return {key: value for key, value in compact.items() if value not in (None, [], {})}


def compact_text(text: str, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."
