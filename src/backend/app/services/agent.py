from __future__ import annotations

"""에이전트 오케스트레이션 — 자체 스킬 호출 방식 (POC)"""
import json
import re
import time
import traceback
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_debug_trace import AgentDebugTrace
from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.intent_turn import IntentTurn
from app.models.message import Message
from app.models.project import Project
from app.services.chat_workspace import (
    append_conversation_message,
    ensure_chat_workspace,
    is_summary_suggested,
)
from app.services.casual_chat import generate_casual_reply
from app.services.context import build_context, get_recent_messages
from app.services.agent_tools import execute_tool
from app.services.intent_turns import (
    RouterDecision,
    ambiguous_reference_question,
    casual_response,
    clarification_question,
    create_intent_turn,
    decide_message_gate,
    record_intent_event,
    route_intent,
    set_intent_status,
    gate_context_payload,
    update_intent_turn_from_route,
)
from app.services.llm import get_client
from app.services.sse import SSEEmitter
from app.services.tool_registry import build_tool_descriptions, normalize_tool_names

MAX_TOOL_ROUNDS = 15


async def _record_debug_trace(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    turn_message_id: str,
    round_index: int,
    event_type: str,
    payload: object,
    duration_ms: float | None = None,
) -> None:
    try:
        db.add(AgentDebugTrace(
            project_id=project.id,
            chat_session_id=chat_session.id,
            turn_message_id=turn_message_id,
            round_index=round_index,
            event_type=event_type,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
            duration_ms=duration_ms,
        ))
        await db.commit()
    except Exception as exc:
        await db.rollback()
        try:
            db.add(AgentLog(
                chat_session_id=chat_session.id,
                round_index=round_index,
                event_type="debug_trace_error",
                content=str(exc)[:2000],
            ))
            await db.commit()
        except Exception:
            await db.rollback()


async def _emit_and_save_assistant(
    db: AsyncSession,
    chat_session: ChatSession,
    workspace: str,
    emitter: SSEEmitter,
    content: str,
) -> Message:
    assistant_msg = Message(chat_session_id=chat_session.id, role="planner", content=content)
    db.add(assistant_msg)
    await db.commit()
    emitter.emit("message_start", {"message_id": assistant_msg.id, "role": "assistant"})
    emitter.emit("message_delta", {"message_id": assistant_msg.id, "content": content})
    emitter.emit("message_end", {"message_id": assistant_msg.id})
    append_conversation_message(workspace, chat_session, "planner", content, assistant_msg.created_at)
    return assistant_msg


def parse_tool_call(text: str) -> dict | None:
    pattern = r"```tool_call\s*\n?(.*?)\n?```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
    return None


def extract_text_without_tool_call(text: str) -> str:
    pattern = r"```tool_call\s*\n?.*?\n?```"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()


def _blocked_tool_result(tool_name: str, selected_tools: list[str]) -> str:
    allowed = ", ".join(selected_tools) or "없음"
    return f"도구 사용 차단: {tool_name}는 이번 intent turn에 선택되지 않았습니다. 선택된 도구: {allowed}"


def _blocked_tool_message(tool_name: str, selected_tools: list[str]) -> str:
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


def _routing_context_instruction(route: RouterDecision) -> str:
    if not route.routing_context:
        return ""
    context = _executor_routing_context(route.routing_context)
    return (
        "\n\n[현재 턴 라우팅 맥락]\n"
        "아래 JSON은 게이트와 라우터가 판단한 현재 턴의 핵심 맥락입니다. "
        "답변이나 도구 호출이 필요하면 이 정보를 근거로 사용하세요.\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2, default=str)}"
    )


def _executor_routing_context(context: dict) -> dict:
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
        compact_gate["reason"] = _compact_text(str(gate_context["reason"]), 360)

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


def _compact_text(text: str, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


async def run_agent(
    db: AsyncSession,
    chat_session: ChatSession,
    project: Project,
    user_content: str,
    emitter: SSEEmitter,
    *,
    debug_enabled: bool = False,
    client_message_id: str | None = None,
) -> None:
    """에이전트 실행 메인 루프 — 자체 스킬 호출 + 스트리밍"""
    turn_message_id: str | None = None
    intent_turn: IntentTurn | None = None
    try:
        ensure_chat_workspace(project.workspace_path, project.user_id, chat_session)
        await db.commit()

        # 1. 사용자 메시지 저장
        user_msg = Message(chat_session_id=chat_session.id, role="user", content=user_content)
        db.add(user_msg)
        await db.commit()
        turn_message_id = user_msg.id
        emitter.emit("user_message_saved", {
            "client_message_id": client_message_id,
            "message_id": user_msg.id,
            "debug_enabled": debug_enabled,
        })
        append_conversation_message(project.workspace_path, chat_session, "user", user_content, user_msg.created_at)

        emitter.emit("status", {"session_status": "routing", "message": "요청 성격을 확인하고 있습니다..."})
        gate = await decide_message_gate(db, chat_session, user_content, workspace=project.workspace_path)
        if debug_enabled and turn_message_id:
            await _record_debug_trace(
                db,
                project,
                chat_session,
                turn_message_id,
                -30,
                "gate_decision",
                {
                    "decision": gate.decision,
                    "reason": gate.reason,
                    "intent_turn_id": gate.intent_turn.id if gate.intent_turn else None,
                    "artifact_path": gate.artifact_path,
                    "artifact_kind": gate.artifact_kind,
                    "artifact_url": gate.artifact_url,
                    "artifact_action": gate.artifact_action,
                    "confidence": gate.confidence,
                    "source": gate.source,
                    "candidates": [
                        {"id": candidate.id, "summary": candidate.summary, "status": candidate.status}
                        for candidate in gate.candidates
                    ],
                },
            )

        if gate.decision == "casual_chat":
            reply = await generate_casual_reply(
                db,
                project,
                chat_session,
                user_content,
                gate_reason=gate.reason,
            )
            await _emit_and_save_assistant(
                db,
                chat_session,
                project.workspace_path,
                emitter,
                reply or casual_response(user_content),
            )
            emitter.emit("done", {"summary": "일반 대화 응답 완료"})
            return

        if gate.decision == "cancel_intent" and gate.intent_turn:
            intent_turn = gate.intent_turn
            await set_intent_status(db, intent_turn, "cancelled")
            await record_intent_event(
                db,
                intent_turn,
                "gate_decision",
                {"decision": gate.decision, "reason": gate.reason},
                message_id=user_msg.id,
            )
            await _emit_and_save_assistant(db, chat_session, project.workspace_path, emitter, "진행 중이던 작업을 취소했습니다.")
            emitter.emit("done", {"summary": "작업 취소"})
            return

        if gate.decision == "ambiguous_reference":
            intent_turn = await create_intent_turn(db, project, chat_session, user_msg)
            await record_intent_event(
                db,
                intent_turn,
                "gate_decision",
                {
                    "decision": gate.decision,
                    "reason": gate.reason,
                    "candidates": [
                        {"id": candidate.id, "summary": candidate.summary, "status": candidate.status}
                        for candidate in gate.candidates
                    ],
                },
                message_id=user_msg.id,
            )
            await set_intent_status(db, intent_turn, "needs_clarification")
            question = ambiguous_reference_question(gate.candidates)
            question_msg = await _emit_and_save_assistant(db, chat_session, project.workspace_path, emitter, question)
            await record_intent_event(
                db,
                intent_turn,
                "clarification_question",
                {"question": question},
                message_id=question_msg.id,
            )
            emitter.emit("done", {"summary": "참조 대상 확인 질문"})
            return

        if gate.decision == "continue_intent" and gate.intent_turn:
            intent_turn = gate.intent_turn
            await record_intent_event(
                db,
                intent_turn,
                "clarification_answer",
                {"answer": user_content},
                message_id=user_msg.id,
            )
        else:
            parent_id = gate.intent_turn.id if gate.decision in {"revive_intent", "artifact_reference", "missing_artifact_reference"} and gate.intent_turn else None
            if gate.decision == "new_task" and gate.intent_turn:
                await set_intent_status(db, gate.intent_turn, "abandoned")
                await record_intent_event(
                    db,
                    gate.intent_turn,
                    "gate_decision",
                    {"decision": "abandoned", "reason": gate.reason},
                    message_id=user_msg.id,
                )
            intent_turn = await create_intent_turn(db, project, chat_session, user_msg, parent_intent_turn_id=parent_id)
            await record_intent_event(
                db,
                intent_turn,
                "gate_decision",
                {
                    "decision": gate.decision,
                    "reason": gate.reason,
                    "parent_intent_turn_id": parent_id,
                    "artifact_path": gate.artifact_path,
                    "artifact_kind": gate.artifact_kind,
                    "artifact_url": gate.artifact_url,
                    "artifact_action": gate.artifact_action,
                    "confidence": gate.confidence,
                    "source": gate.source,
                },
                message_id=user_msg.id,
            )

        route = await route_intent(
            db,
            project,
            chat_session,
            user_content,
            previous_turn=gate.intent_turn,
            gate_context=gate_context_payload(gate),
        )
        await record_intent_event(
            db,
            intent_turn,
            "router_result",
            {
                "intent": route.intent,
                "confidence": route.confidence,
                "can_execute": route.can_execute,
                "selected_tools": route.selected_tools,
                "selected_skills": route.selected_skills,
                "missing_info": route.missing_info,
                "risk_level": route.risk_level,
                "question": route.question,
                "reason": route.reason,
                "source": route.source,
                "invalid_tools": route.invalid_tools,
            },
            message_id=user_msg.id,
            debug_payload={
                "user_content": user_content,
                "tool_selection_source": route.source,
                "routing_context": route.routing_context,
            } if debug_enabled else None,
        )

        if not route.can_execute:
            await update_intent_turn_from_route(db, intent_turn, route, "needs_clarification")
            question = clarification_question(route)
            question_msg = await _emit_and_save_assistant(db, chat_session, project.workspace_path, emitter, question)
            await record_intent_event(
                db,
                intent_turn,
                "clarification_question",
                {"question": question, "missing_info": route.missing_info},
                message_id=question_msg.id,
            )
            emitter.emit("done", {"summary": "추가 정보 질문"})
            return

        selected_tools = normalize_tool_names(route.selected_tools)
        await update_intent_turn_from_route(db, intent_turn, route, "executing")
        await record_intent_event(
            db,
            intent_turn,
            "selected_tools",
            {"selected_tools": selected_tools, "selected_skills": route.selected_skills},
            message_id=user_msg.id,
        )

        emitter.emit("status", {"session_status": "planning", "message": "요청을 분석하고 있습니다..."})

        # 2. 시스템 컨텍스트 조립 (프로젝트의 워크스페이스 사용)
        system_parts = await build_context(db, project, chat_session)
        system_instruction = "\n".join(system_parts) + "\n" + build_tool_descriptions(selected_tools) + _routing_context_instruction(route)

        # 3. 최근 대화 히스토리 (채팅 세션의 메시지 사용)
        recent = await get_recent_messages(db, chat_session.id)

        # 4. 대화 히스토리 구성
        contents = []
        for msg in recent:
            contents.append({"role": msg["role"], "parts": [{"text": msg["text"]}]})
        if not recent or recent[-1]["role"] != "user" or recent[-1]["text"] != user_content:
            contents.append({"role": "user", "parts": [{"text": user_content}]})

        # 5. Tool calling 루프
        client = get_client()
        model_name = "gemini-3-flash-preview"
        generation_config = {"system_instruction": system_instruction, "temperature": 0.7}

        for round_num in range(MAX_TOOL_ROUNDS):
            full_text = ""
            msg_id = str(uuid.uuid4())
            started = False
            import asyncio

            # 로그: LLM 요청
            llm_input = contents[-1]["parts"][0]["text"] if contents else ""
            db.add(AgentLog(chat_session_id=chat_session.id, round_index=round_num, event_type="llm_request", content=llm_input[:2000]))
            await db.commit()
            if debug_enabled and turn_message_id:
                await _record_debug_trace(
                    db,
                    project,
                    chat_session,
                    turn_message_id,
                    round_num,
                    "llm_request",
                    {
                        "model": model_name,
                        "system_instruction": system_instruction,
                        "contents": contents,
                        "config": generation_config,
                    },
                )

            t0 = time.time()
            stream = client.models.generate_content_stream(
                model=model_name,
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
                        # tool_call 앞의 아직 안 보낸 텍스트가 있으면 보내기
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

            tool_call = parse_tool_call(full_text)
            if debug_enabled and turn_message_id:
                await _record_debug_trace(
                    db,
                    project,
                    chat_session,
                    turn_message_id,
                    round_num,
                    "llm_response",
                    {
                        "text": full_text,
                        "has_tool_call": tool_call is not None,
                        "parsed_tool_call": tool_call,
                    },
                    duration_ms=llm_ms,
                )

            if tool_call is None:
                if full_text.strip():
                    assistant_msg = Message(chat_session_id=chat_session.id, role="planner", content=full_text.strip())
                    db.add(assistant_msg)
                    await db.commit()
                    append_conversation_message(project.workspace_path, chat_session, "planner", full_text.strip(), assistant_msg.created_at)
                break

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
                await _record_debug_trace(
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
                result = _blocked_tool_result(tool_name, selected_tools)
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
                await _record_debug_trace(
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

            if tool_blocked:
                final_message = _blocked_tool_message(tool_name, selected_tools)
                await _emit_and_save_assistant(db, chat_session, project.workspace_path, emitter, final_message)
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
                return

            contents.append({"role": "model", "parts": [{"text": full_text}]})
            contents.append({"role": "user", "parts": [{"text": f"[도구 실행 결과]\n{result}"}]})

        if intent_turn:
            await set_intent_status(db, intent_turn, "completed")
            await record_intent_event(
                db,
                intent_turn,
                "result",
                {"summary": "작업이 완료되었습니다."},
                message_id=turn_message_id,
            )

        recent_total_result = await db.execute(
            select(func.count(Message.id)).where(Message.chat_session_id == chat_session.id, Message.compressed == False)
        )
        recent_total = recent_total_result.scalar() or 0
        if is_summary_suggested(recent_total):
            emitter.emit("summary_suggested", {
                "message": "채팅이 길어졌습니다. 요약해서 맥락을 압축할 수 있습니다.",
                "chat_id": chat_session.id,
            })

        emitter.emit("done", {"summary": "작업이 완료되었습니다."})

    except Exception as e:
        traceback.print_exc()
        try:
            db.add(AgentLog(chat_session_id=chat_session.id, round_index=-1, event_type="error", content=str(e)[:2000]))
            await db.commit()
        except Exception:
            await db.rollback()
        if intent_turn:
            try:
                await set_intent_status(db, intent_turn, "failed")
                await record_intent_event(
                    db,
                    intent_turn,
                    "error",
                    {"message": str(e)},
                    message_id=turn_message_id,
                    debug_payload={"traceback": traceback.format_exc()} if debug_enabled else None,
                )
            except Exception:
                await db.rollback()
        if debug_enabled and turn_message_id:
            await _record_debug_trace(
                db,
                project,
                chat_session,
                turn_message_id,
                -1,
                "error",
                {"message": str(e), "traceback": traceback.format_exc()},
            )
        emitter.emit("error", {"code": "AGENT_ERROR", "message": str(e)})
    finally:
        emitter.done()
