from __future__ import annotations

import asyncio
import json
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.intent_turn import IntentTurn
from app.models.message import Message
from app.models.project import Project
from app.services.agent_events import emit_and_save_assistant, record_debug_trace
from app.services.agent_response import (
    blocked_tool_message,
    blocked_tool_result,
    extract_text_without_tool_call,
    parse_tool_call_result,
    routing_context_instruction,
)
from app.services.agent_tools import execute_tool
from app.services.chat_workspace import append_conversation_message
from app.services.context import build_context, get_recent_messages
from app.services.intent_turns import RouterDecision, record_intent_event, set_intent_status
from app.services.llm import get_client
from app.services.sse import SSEEmitter
from app.services.tool_registry import build_tool_descriptions

MAX_TOOL_ROUNDS = 15
MAX_TOOL_PARSE_REPAIR_ATTEMPTS = 1
MODEL_NAME = "gemini-3-flash-preview"


async def run_tool_call_loop(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    intent_turn: IntentTurn | None,
    turn_message_id: str | None,
    user_content: str,
    route: RouterDecision,
    selected_tools: list[str],
    emitter: SSEEmitter,
    *,
    debug_enabled: bool,
) -> str:
    system_parts = await build_context(db, project, chat_session)
    system_instruction = "\n".join(system_parts) + "\n" + build_tool_descriptions(selected_tools) + routing_context_instruction(route)
    recent = await get_recent_messages(db, chat_session.id)
    contents = build_model_contents(recent, user_content)

    client = get_client()
    generation_config = {"system_instruction": system_instruction, "temperature": 0.7}
    parse_repair_attempts = 0
    expecting_parse_repair = False

    for round_num in range(MAX_TOOL_ROUNDS):
        full_text, llm_ms = await _stream_llm_round(
            db,
            project,
            chat_session,
            turn_message_id,
            contents,
            generation_config,
            emitter,
            round_num,
            debug_enabled=debug_enabled,
        )

        parse_result = parse_tool_call_result(full_text)
        tool_call = parse_result.tool_call
        if debug_enabled and turn_message_id:
            await record_debug_trace(
                db,
                project,
                chat_session,
                turn_message_id,
                round_num,
                "llm_response",
                {
                    "text": full_text,
                    "has_tool_call": tool_call is not None,
                    "has_tool_call_block": parse_result.has_block,
                    "tool_call_parse_ok": tool_call is not None,
                    "tool_call_parse_error": parse_result.error,
                    "parsed_tool_call": tool_call,
                },
                duration_ms=llm_ms,
            )

        if parse_result.has_block and tool_call is None:
            await _record_tool_call_parse_error(
                db,
                project,
                chat_session,
                intent_turn,
                turn_message_id,
                round_num,
                parse_result.error,
                parse_result.raw_block,
                debug_enabled=debug_enabled,
            )
            if parse_repair_attempts < MAX_TOOL_PARSE_REPAIR_ATTEMPTS:
                parse_repair_attempts += 1
                expecting_parse_repair = True
                contents.append({"role": "model", "parts": [{"text": full_text}]})
                contents.append({"role": "user", "parts": [{"text": _tool_call_parse_repair_message(parse_result.error)}]})
                continue

            await _handle_tool_call_parse_failure(
                db,
                project,
                chat_session,
                intent_turn,
                turn_message_id,
                emitter,
                parse_result.error,
                parse_result.raw_block,
                debug_enabled=debug_enabled,
            )
            return "failed"

        if tool_call is None:
            if expecting_parse_repair:
                await _handle_tool_call_parse_failure(
                    db,
                    project,
                    chat_session,
                    intent_turn,
                    turn_message_id,
                    emitter,
                    "교정 응답에 tool_call 블록이 없습니다.",
                    None,
                    debug_enabled=debug_enabled,
                )
                return "failed"
            if full_text.strip():
                assistant_msg = Message(chat_session_id=chat_session.id, role="planner", content=full_text.strip())
                db.add(assistant_msg)
                await db.commit()
                append_conversation_message(project.workspace_path, chat_session, "planner", full_text.strip(), assistant_msg.created_at)
            break

        expecting_parse_repair = False
        loop_result = await _execute_tool_call(
            db,
            project,
            chat_session,
            intent_turn,
            turn_message_id,
            full_text,
            tool_call,
            selected_tools,
            emitter,
            round_num,
            debug_enabled=debug_enabled,
        )
        if loop_result == "blocked":
            return "blocked"

        contents.append({"role": "model", "parts": [{"text": full_text}]})
        contents.append({"role": "user", "parts": [{"text": f"[도구 실행 결과]\n{loop_result}"}]})

    return "completed"


def _tool_call_parse_repair_message(error: str | None) -> str:
    error_text = error or "JSON 파싱에 실패했습니다."
    return (
        "[도구 호출 형식 오류]\n"
        "직전 응답의 tool_call 블록은 유효한 JSON이 아니어서 실행되지 않았습니다.\n"
        f"오류: {error_text}\n"
        "도구 호출만 다시 작성하세요. 설명 없이 정확히 하나의 ```tool_call fenced block으로 끝내세요.\n"
        "JSON 문자열 안의 백슬래시는 반드시 유효하게 escape하세요. 예를 들어 CSS/HTML content 안에 "
        "불필요한 `\\ ` 조합을 넣지 마세요."
    )


def _tool_call_parse_failure_message() -> str:
    return (
        "도구 호출 형식 오류가 반복되어 요청한 작업을 실행하지 못했습니다. "
        "파일이나 폴더 변경은 수행되지 않았습니다. 다시 요청해 주시면 이어서 처리하겠습니다."
    )


def _preview_text(text: str | None, limit: int = 2000) -> str | None:
    if text is None:
        return None
    return text if len(text) <= limit else text[:limit] + "... (truncated)"


async def _record_tool_call_parse_error(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    intent_turn: IntentTurn | None,
    turn_message_id: str | None,
    round_num: int,
    error: str | None,
    raw_block: str | None,
    *,
    debug_enabled: bool,
) -> None:
    payload = {"error": error or "도구 호출 JSON 파싱 실패"}
    if debug_enabled and turn_message_id:
        await record_debug_trace(
            db,
            project,
            chat_session,
            turn_message_id,
            round_num,
            "tool_call_parse_error",
            {**payload, "raw_block": _preview_text(raw_block)},
        )
    if intent_turn:
        await record_intent_event(
            db,
            intent_turn,
            "tool_call_parse_error",
            {"reason": "LLM 응답의 tool_call 블록을 파싱하지 못했습니다."},
            message_id=turn_message_id,
            debug_payload={**payload, "raw_block": _preview_text(raw_block)} if debug_enabled else None,
        )


async def _handle_tool_call_parse_failure(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    intent_turn: IntentTurn | None,
    turn_message_id: str | None,
    emitter: SSEEmitter,
    error: str | None,
    raw_block: str | None,
    *,
    debug_enabled: bool,
) -> None:
    final_message = _tool_call_parse_failure_message()
    await emit_and_save_assistant(db, chat_session, project.workspace_path, emitter, final_message)
    if intent_turn:
        await set_intent_status(db, intent_turn, "failed")
        await record_intent_event(
            db,
            intent_turn,
            "failed",
            {"reason": "도구 호출 형식 오류가 반복되어 작업을 실행하지 못했습니다."},
            message_id=turn_message_id,
            debug_payload={"error": error, "raw_block": _preview_text(raw_block)} if debug_enabled else None,
        )
    if debug_enabled and turn_message_id:
        await record_debug_trace(
            db,
            project,
            chat_session,
            turn_message_id,
            -1,
            "tool_call_parse_failed",
            {"error": error, "raw_block": _preview_text(raw_block)},
        )
    emitter.emit("done", {"summary": "도구 호출 형식 오류로 작업이 중단되었습니다."})


def build_model_contents(recent: list[dict], user_content: str) -> list[dict]:
    contents = [{"role": msg["role"], "parts": [{"text": msg["text"]}]} for msg in recent]
    if not recent or recent[-1]["role"] != "user" or recent[-1]["text"] != user_content:
        contents.append({"role": "user", "parts": [{"text": user_content}]})
    return contents


async def _stream_llm_round(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    turn_message_id: str | None,
    contents: list[dict],
    generation_config: dict,
    emitter: SSEEmitter,
    round_num: int,
    *,
    debug_enabled: bool,
) -> tuple[str, float]:
    full_text = ""
    msg_id = str(uuid.uuid4())
    started = False
    llm_input = contents[-1]["parts"][0]["text"] if contents else ""

    db.add(AgentLog(chat_session_id=chat_session.id, round_index=round_num, event_type="llm_request", content=llm_input[:2000]))
    await db.commit()
    if debug_enabled and turn_message_id:
        await record_debug_trace(
            db,
            project,
            chat_session,
            turn_message_id,
            round_num,
            "llm_request",
            {
                "model": MODEL_NAME,
                "system_instruction": generation_config["system_instruction"],
                "contents": contents,
                "config": generation_config,
            },
        )

    t0 = time.time()
    stream = get_client().models.generate_content_stream(
        model=MODEL_NAME,
        contents=contents,
        config=generation_config,
    )

    for chunk in stream:
        if not chunk.text:
            continue
        chunk_text = chunk.text
        full_text += chunk_text

        if "```tool_call" in full_text:
            if started:
                pre_tool = full_text.split("```tool_call")[0]
                already_sent_len = len(full_text) - len(chunk_text)
                remaining = pre_tool[already_sent_len:]
                if remaining.strip():
                    emitter.emit("message_delta", {"message_id": msg_id, "content": remaining})
                emitter.emit("message_end", {"message_id": msg_id})
                started = False
            continue

        if not started:
            emitter.emit("message_start", {"message_id": msg_id, "role": "assistant"})
            started = True
        emitter.emit("message_delta", {"message_id": msg_id, "content": chunk_text})
        await asyncio.sleep(0)

    if started:
        emitter.emit("message_end", {"message_id": msg_id})

    llm_ms = (time.time() - t0) * 1000
    db.add(AgentLog(chat_session_id=chat_session.id, round_index=round_num, event_type="llm_response", content=full_text[:4000], duration_ms=llm_ms))
    await db.commit()
    return full_text, llm_ms


async def _execute_tool_call(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    intent_turn: IntentTurn | None,
    turn_message_id: str | None,
    full_text: str,
    tool_call: dict,
    selected_tools: list[str],
    emitter: SSEEmitter,
    round_num: int,
    *,
    debug_enabled: bool,
) -> str:
    tool_name = tool_call.get("tool", "")
    tool_args = tool_call.get("args", {})
    tool_blocked = tool_name not in selected_tools

    pre_text = extract_text_without_tool_call(full_text).strip()
    if pre_text and not tool_blocked:
        assistant_msg = Message(chat_session_id=chat_session.id, role="planner", content=pre_text)
        db.add(assistant_msg)
        await db.commit()
        append_conversation_message(project.workspace_path, chat_session, "planner", pre_text, assistant_msg.created_at)

    emitter.emit("status", {"session_status": "executing", "message": f"{tool_name} 실행 중..."})
    emitter.emit("todo_step_updated", {
        "todo_id": "auto",
        "step": {"description": f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)[:80]})", "status": "in_progress"},
    })

    db.add(AgentLog(chat_session_id=chat_session.id, round_index=round_num, event_type="tool_call", content=json.dumps({"tool": tool_name, "args": tool_args}, ensure_ascii=False)[:2000]))
    await db.commit()
    if debug_enabled and turn_message_id:
        await record_debug_trace(
            db,
            project,
            chat_session,
            turn_message_id,
            round_num,
            "tool_call",
            {"tool": tool_name, "args": tool_args},
        )

    t1 = time.time()
    if tool_blocked:
        result = blocked_tool_result(tool_name, selected_tools)
    else:
        result = await execute_tool(
            project.workspace_path,
            tool_name,
            tool_args,
            emitter,
            db=db,
            project=project,
            chat_session=chat_session,
        )
    tool_ms = (time.time() - t1) * 1000

    db.add(AgentLog(chat_session_id=chat_session.id, round_index=round_num, event_type="tool_result", content=json.dumps({"tool": tool_name, "result": result[:1000]}, ensure_ascii=False), duration_ms=tool_ms))
    await db.commit()
    if debug_enabled and turn_message_id:
        await record_debug_trace(
            db,
            project,
            chat_session,
            turn_message_id,
            round_num,
            "tool_result",
            {"tool": tool_name, "result": result},
            duration_ms=tool_ms,
        )

    emitter.emit("todo_step_updated", {
        "todo_id": "auto",
        "step": {
            "description": f"{tool_name} 차단됨" if tool_blocked else f"{tool_name} 완료",
            "status": "blocked" if tool_blocked else "completed",
        },
    })

    if not tool_blocked:
        return result

    final_message = blocked_tool_message(tool_name, selected_tools)
    await emit_and_save_assistant(db, chat_session, project.workspace_path, emitter, final_message)
    if intent_turn:
        await record_intent_event(
            db,
            intent_turn,
            "tool_selection_mismatch",
            {
                "requested_tool": tool_name,
                "selected_tools": selected_tools,
                "reason": "LLM 실행 응답이 라우터가 선택한 도구 목록 밖의 도구를 호출했습니다.",
            },
            message_id=turn_message_id,
        )
        await set_intent_status(db, intent_turn, "blocked")
        await record_intent_event(
            db,
            intent_turn,
            "blocked",
            {"tool": tool_name, "selected_tools": selected_tools, "reason": result},
            message_id=turn_message_id,
        )
    emitter.emit("done", {"summary": "선택되지 않은 도구 호출로 작업이 중단되었습니다."})
    return "blocked"
