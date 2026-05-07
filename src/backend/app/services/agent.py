from __future__ import annotations

"""에이전트 오케스트레이션 — 자체 스킬 호출 방식 (현재 구현)"""
import traceback

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.agent_events import (
    emit_and_save_assistant as _emit_and_save_assistant,
    record_debug_trace as _record_debug_trace,
)
from app.services.agent_tool_loop import run_tool_call_loop
from app.services.intent_turns import (
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
from app.services.sse import SSEEmitter
from app.services.tool_registry import normalize_tool_names


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

        loop_status = await run_tool_call_loop(
            db,
            project,
            chat_session,
            intent_turn,
            turn_message_id,
            user_content,
            route,
            selected_tools,
            emitter,
            debug_enabled=debug_enabled,
        )
        if loop_status == "blocked":
            return

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
