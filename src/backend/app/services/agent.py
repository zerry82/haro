from __future__ import annotations

"""에이전트 오케스트레이션 — 자체 스킬 호출 방식 (현재 구현)"""
import traceback
import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.intent_turn import IntentTurn
from app.models.message import Message
from app.models.plan_mode import PlanSession
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
from app.services.file_discovery_context import sanitize_open_file_context
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
from app.services.intent_types import RouterDecision
from app.services.plan_mode import (
    EXECUTION_COMPLETED,
    EXECUTION_FAILED,
    EXECUTION_RUNNING,
    PLAN_AWAITING_APPROVAL,
    PLAN_DRAFTING,
    PLAN_MODE_SELECTED_TOOLS,
    REQUIREMENTS_CLARIFYING,
    approve_plan,
    build_execution_instruction,
    create_plan_session,
    get_current_plan_session,
    get_plan_session,
    plan_has_successful_evidence,
    read_plan_file,
    reject_plan,
    set_plan_status,
    validate_plan_for_approval,
)
from app.services.sse import SSEEmitter
from app.services.tool_registry import normalize_tool_names


def _plan_mode_route(reason: str | None = None) -> RouterDecision:
    return RouterDecision(
        intent="plan_mode",
        confidence=1.0,
        can_execute=True,
        selected_tools=PLAN_MODE_SELECTED_TOOLS,
        selected_skills=[],
        missing_info=[],
        risk_level="low",
        question=None,
        reason=reason or "Plan Mode에서 승인 전 계획을 작성합니다.",
        source="plan_mode",
        should_enter_plan_mode=True,
        plan_mode_reason=reason,
        execution_policy="plan_mode",
        context_confidence=1.0,
        target_confidence=1.0,
        source_confidence=1.0,
        operation_confidence=1.0,
    )


def _is_plan_approval_text(content: str) -> bool:
    normalized = " ".join((content or "").lower().split())
    return normalized in {"승인", "승인해", "승인할게", "approve", "approved", "진행", "진행해", "실행", "실행해", "go"}


def _emit_plan_session(emitter: SSEEmitter, event: str, plan_session: PlanSession, **extra) -> None:
    emitter.emit(
        event,
        {
            "plan_session_id": plan_session.id,
            "status": plan_session.status,
            "plan_file_path": plan_session.plan_file_path,
            **extra,
        },
    )


async def _record_file_discovery_events(
    db: AsyncSession,
    intent_turn: IntentTurn | None,
    message_id: str,
    routing_context: dict | None,
) -> None:
    if not intent_turn or not routing_context:
        return
    discovery = routing_context.get("file_discovery_context")
    if not isinstance(discovery, dict):
        return
    candidates = discovery.get("candidates") or []
    await record_intent_event(
        db,
        intent_turn,
        "file_discovery_candidates",
        {"candidates": candidates[:8]},
        message_id=message_id,
    )
    search_plan = discovery.get("search_plan") or []
    if search_plan:
        await record_intent_event(
            db,
            intent_turn,
            "file_search_plan",
            {"steps": search_plan},
            message_id=message_id,
        )
    if discovery.get("source_content_missing"):
        await record_intent_event(
            db,
            intent_turn,
            "file_search_exhausted",
            {
                "reason": "File Discovery Context가 source content 후보를 찾지 못했습니다.",
                "missing_info": discovery.get("missing_info") or [],
            },
            message_id=message_id,
        )


async def _run_plan_mode_turn(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    user_msg: Message,
    user_content: str,
    emitter: SSEEmitter,
    *,
    debug_enabled: bool,
    plan_session: PlanSession,
    plan_feedback: str | None = None,
    intent_turn: IntentTurn | None = None,
) -> str:
    if intent_turn is None:
        intent_turn = await create_intent_turn(db, project, chat_session, user_msg)
        await record_intent_event(
            db,
            intent_turn,
            "plan_mode_context",
            {"plan_session_id": plan_session.id, "feedback": plan_feedback},
            message_id=user_msg.id,
        )

    if not plan_session.intent_turn_id:
        plan_session.intent_turn_id = intent_turn.id
        await db.commit()

    route = _plan_mode_route("승인 전 계획 수립 단계입니다.")
    selected_tools = normalize_tool_names(route.selected_tools)
    await update_intent_turn_from_route(db, intent_turn, route, "executing")
    await record_intent_event(
        db,
        intent_turn,
        "selected_tools",
        {"selected_tools": selected_tools, "selected_skills": route.selected_skills},
        message_id=user_msg.id,
    )

    emitter.emit("status", {"session_status": PLAN_DRAFTING, "message": "계획을 작성하고 있습니다..."})
    loop_status = await run_tool_call_loop(
        db,
        project,
        chat_session,
        intent_turn,
        user_msg.id,
        user_content,
        route,
        selected_tools,
        emitter,
        debug_enabled=debug_enabled,
        plan_session=plan_session,
        plan_feedback=plan_feedback,
    )

    if loop_status == PLAN_AWAITING_APPROVAL:
        await set_intent_status(db, intent_turn, "waiting_review")
        await record_intent_event(
            db,
            intent_turn,
            "plan_approval_requested",
            {"plan_session_id": plan_session.id},
            message_id=user_msg.id,
        )
        return loop_status
    if loop_status in {"blocked", "failed"}:
        return loop_status

    await set_intent_status(db, intent_turn, "completed")
    await record_intent_event(
        db,
        intent_turn,
        "result",
        {"summary": "계획 작성 라운드가 완료되었습니다.", "plan_session_id": plan_session.id},
        message_id=user_msg.id,
    )
    return loop_status


async def _run_approved_plan_execution(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    user_msg: Message,
    emitter: SSEEmitter,
    *,
    debug_enabled: bool,
    plan_session: PlanSession,
) -> str:
    plan_content = read_plan_file(project.workspace_path, plan_session)
    execution_content = build_execution_instruction(plan_content)
    intent_turn = await create_intent_turn(db, project, chat_session, user_msg, parent_intent_turn_id=plan_session.intent_turn_id)
    has_evidence = await plan_has_successful_evidence(db, plan_session)
    validation = validate_plan_for_approval(plan_session, plan_content, has_successful_evidence=has_evidence)
    if not validation.ok:
        reason = validation.reason or "승인된 계획의 요구사항/근거 검증을 통과하지 못했습니다."
        await _emit_and_save_assistant(db, chat_session, project.workspace_path, emitter, reason)
        await set_intent_status(db, intent_turn, "blocked")
        await record_intent_event(
            db,
            intent_turn,
            "execution_blocked",
            {"reason": reason, "plan_session_id": plan_session.id, "validation": validation.payload or {}},
            message_id=user_msg.id,
        )
        await set_plan_status(
            db,
            plan_session,
            EXECUTION_FAILED,
            event_type=(
                "acceptance_check_failed"
                if not (validation.payload or {}).get("acceptance_checks_present", True)
                else "evidence_missing"
                if (validation.payload or {}).get("evidence_required")
                else "requirements_question_required"
            ),
            payload={"reason": reason, "validation": validation.payload or {}},
        )
        emitter.emit("execution_blocked", {"tool": "approved_plan_execution", "reason": reason})
        return "blocked"
    await set_plan_status(
        db,
        plan_session,
        EXECUTION_RUNNING,
        event_type="plan_mode_exited",
        payload={"reason": "approved"},
    )
    _emit_plan_session(emitter, "plan_mode_exited", plan_session, reason="approved")

    route = await route_intent(
        db,
        project,
        chat_session,
        execution_content,
        gate_context={"decision": "plan_approved", "plan_session_id": plan_session.id},
    )
    route.should_enter_plan_mode = False
    route.plan_mode_reason = None

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
            "execution_policy": route.execution_policy,
            "context_confidence": route.context_confidence,
            "target_confidence": route.target_confidence,
            "source_confidence": route.source_confidence,
            "operation_confidence": route.operation_confidence,
            "should_enter_plan_mode": False,
            "plan_mode_reason": None,
        },
        message_id=user_msg.id,
        debug_payload={
            "user_content": execution_content,
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
        await set_plan_status(db, plan_session, EXECUTION_FAILED, event_type="execution_blocked", payload={"reason": question})
        return "blocked"

    selected_tools = normalize_tool_names(route.selected_tools)
    await update_intent_turn_from_route(db, intent_turn, route, "executing")
    await record_intent_event(
        db,
        intent_turn,
        "selected_tools",
        {"selected_tools": selected_tools, "selected_skills": route.selected_skills},
        message_id=user_msg.id,
    )

    emitter.emit("status", {"session_status": EXECUTION_RUNNING, "message": "승인된 계획을 실행하고 있습니다..."})
    loop_status = await run_tool_call_loop(
        db,
        project,
        chat_session,
        intent_turn,
        user_msg.id,
        execution_content,
        route,
        selected_tools,
        emitter,
        debug_enabled=debug_enabled,
        execution_plan_content=plan_content,
    )
    if loop_status in {"blocked", "failed"}:
        await set_plan_status(db, plan_session, EXECUTION_FAILED, event_type="execution_blocked", payload={"status": loop_status})
        return loop_status

    await set_intent_status(db, intent_turn, "completed")
    await record_intent_event(
        db,
        intent_turn,
        "result",
        {"summary": "승인된 계획 실행이 완료되었습니다.", "plan_session_id": plan_session.id},
        message_id=user_msg.id,
    )
    await set_plan_status(db, plan_session, EXECUTION_COMPLETED, event_type="final_report_created", payload={"summary": "작업이 완료되었습니다."})
    _emit_plan_session(emitter, "execution_completed", plan_session)
    return "completed"


async def run_agent(
    db: AsyncSession,
    chat_session: ChatSession,
    project: Project,
    user_content: str,
    emitter: SSEEmitter,
    *,
    debug_enabled: bool = False,
    client_message_id: str | None = None,
    plan_mode_requested: bool = False,
    plan_response: dict | None = None,
    open_file_context: dict | None = None,
) -> None:
    """에이전트 실행 메인 루프 — 자체 스킬 호출 + 스트리밍"""
    turn_message_id: str | None = None
    intent_turn: IntentTurn | None = None
    try:
        ensure_chat_workspace(project.workspace_path, project.user_id, chat_session)
        await db.commit()

        # 1. 사용자 메시지 저장
        sanitized_open_file_context = sanitize_open_file_context(open_file_context, project.user_id)
        message_metadata = {
            "client_message_id": client_message_id,
            "debug_enabled": debug_enabled,
        }
        if sanitized_open_file_context:
            message_metadata["open_file_context"] = sanitized_open_file_context
        user_msg = Message(
            chat_session_id=chat_session.id,
            role="user",
            content=user_content,
            metadata_json=json.dumps(message_metadata, ensure_ascii=False),
        )
        db.add(user_msg)
        await db.commit()
        turn_message_id = user_msg.id
        emitter.emit("user_message_saved", {
            "client_message_id": client_message_id,
            "message_id": user_msg.id,
            "debug_enabled": debug_enabled,
        })
        append_conversation_message(project.workspace_path, chat_session, "user", user_content, user_msg.created_at)

        current_plan = await get_current_plan_session(db, chat_session.id)
        if plan_response:
            plan_session_id = str(plan_response.get("plan_session_id") or "")
            action = str(plan_response.get("action") or "").lower()
            feedback = plan_response.get("feedback")
            plan_session = (
                await get_plan_session(db, chat_session.id, plan_session_id)
                if plan_session_id
                else current_plan
            )
            if not plan_session:
                emitter.emit("error", {"code": "PLAN_SESSION_NOT_FOUND", "message": "처리할 Plan Mode 세션을 찾지 못했습니다."})
                emitter.emit("done", {"summary": "Plan Mode 세션 없음"})
                return
            if action == "approve":
                await approve_plan(db, plan_session, message_id=user_msg.id)
                _emit_plan_session(emitter, "plan_approved", plan_session)
                loop_status = await _run_approved_plan_execution(
                    db,
                    project,
                    chat_session,
                    user_msg,
                    emitter,
                    debug_enabled=debug_enabled,
                    plan_session=plan_session,
                )
                if loop_status in {"blocked", "failed"}:
                    return
                emitter.emit("done", {"summary": "승인된 계획 실행 완료"})
                return
            if action == "reject":
                await reject_plan(db, plan_session, message_id=user_msg.id, feedback=str(feedback or user_content or ""))
                _emit_plan_session(emitter, "plan_rejected", plan_session, feedback=feedback)
                await _run_plan_mode_turn(
                    db,
                    project,
                    chat_session,
                    user_msg,
                    user_content,
                    emitter,
                    debug_enabled=debug_enabled,
                    plan_session=plan_session,
                    plan_feedback=str(feedback or user_content or ""),
                )
                emitter.emit("done", {"summary": "계획 피드백 반영"})
                return
            emitter.emit("error", {"code": "INVALID_PLAN_RESPONSE", "message": "Plan Mode 응답 형식이 올바르지 않습니다."})
            emitter.emit("done", {"summary": "Plan Mode 응답 오류"})
            return

        if current_plan and current_plan.status in {REQUIREMENTS_CLARIFYING, PLAN_DRAFTING, PLAN_AWAITING_APPROVAL}:
            if current_plan.status == PLAN_AWAITING_APPROVAL and _is_plan_approval_text(user_content):
                await approve_plan(db, current_plan, message_id=user_msg.id)
                _emit_plan_session(emitter, "plan_approved", current_plan)
                loop_status = await _run_approved_plan_execution(
                    db,
                    project,
                    chat_session,
                    user_msg,
                    emitter,
                    debug_enabled=debug_enabled,
                    plan_session=current_plan,
                )
                if loop_status in {"blocked", "failed"}:
                    return
                emitter.emit("done", {"summary": "승인된 계획 실행 완료"})
                return
            if current_plan.status == PLAN_AWAITING_APPROVAL:
                await reject_plan(db, current_plan, message_id=user_msg.id, feedback=user_content)
                _emit_plan_session(emitter, "plan_rejected", current_plan, feedback=user_content)
            await _run_plan_mode_turn(
                db,
                project,
                chat_session,
                user_msg,
                user_content,
                emitter,
                debug_enabled=debug_enabled,
                plan_session=current_plan,
                plan_feedback=user_content,
            )
            emitter.emit("done", {"summary": "Plan Mode 피드백 처리 완료"})
            return

        emitter.emit("status", {"session_status": "routing", "message": "요청 성격을 확인하고 있습니다..."})
        gate = await decide_message_gate(
            db,
            chat_session,
            user_content,
            workspace=project.workspace_path,
            user_id=project.user_id,
            open_file_context=sanitized_open_file_context,
        )
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
            open_file_context=sanitized_open_file_context,
        )
        await _record_file_discovery_events(db, intent_turn, user_msg.id, route.routing_context)
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
                "execution_policy": route.execution_policy,
                "context_confidence": route.context_confidence,
                "target_confidence": route.target_confidence,
                "source_confidence": route.source_confidence,
                "operation_confidence": route.operation_confidence,
                "should_enter_plan_mode": route.should_enter_plan_mode,
                "plan_mode_reason": route.plan_mode_reason,
            },
            message_id=user_msg.id,
            debug_payload={
                "user_content": user_content,
                "tool_selection_source": route.source,
                "routing_context": route.routing_context,
            } if debug_enabled else None,
        )

        if plan_mode_requested or route.should_enter_plan_mode:
            plan_session = await create_plan_session(
                db,
                project,
                chat_session,
                user_msg,
                trigger_source="ui_toggle" if plan_mode_requested else "router_suggested",
                intent_turn_id=intent_turn.id,
                reason=route.plan_mode_reason,
            )
            _emit_plan_session(
                emitter,
                "plan_mode_entered",
                plan_session,
                reason=route.plan_mode_reason,
                trigger_source=plan_session.trigger_source,
            )
            await _run_plan_mode_turn(
                db,
                project,
                chat_session,
                user_msg,
                user_content,
                emitter,
                debug_enabled=debug_enabled,
                plan_session=plan_session,
                intent_turn=intent_turn,
            )
            emitter.emit("done", {"summary": "Plan Mode 라운드 완료"})
            return

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
        if loop_status in {"blocked", "failed"}:
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
