from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.intent_turn import IntentTurn, IntentTurnEvent
from app.models.message import Message
from app.models.project import Project
from app.services.chat_workspace import get_latest_chat_output_reference
from app.services.intent_gate import LlmGateResult, decide_gate_with_llm
from app.services.intent_resolution import build_resolved_intent_context, ResolvedIntentContext
from app.services.intent_router import fallback_router_decision, llm_route, rule_route
from app.services.intent_text_rules import (
    ambiguous_reference_question,
    casual_response,
    clarification_question,
    is_cancel,
    is_casual_chat,
    looks_like_artifact_reference,
    looks_like_reference,
    normalize,
    now,
    reference_candidates,
    summarize_text,
)
from app.services.intent_types import GateDecision, RECENT_INTENT_LIMIT, RouterDecision
from app.services.tool_registry import normalize_tool_names


async def decide_message_gate(
    db: AsyncSession,
    chat_session: ChatSession,
    content: str,
    *,
    workspace: str | None = None,
    user_id: str | None = None,
    open_file_context: dict[str, Any] | None = None,
    open_mail_context: dict[str, Any] | None = None,
) -> GateDecision:
    normalized = normalize(content)
    waiting = await _get_waiting_intent(db, chat_session.id)
    recent = await get_recent_intent_turns(db, chat_session.id)
    resolved = await build_resolved_intent_context(
        db,
        None,
        chat_session,
        content,
        workspace=workspace,
        previous_turn=waiting,
        recent_turns=recent,
        user_id=user_id,
        open_file_context=open_file_context,
        open_mail_context=open_mail_context,
    )

    llm_gate = await decide_gate_with_llm(resolved)
    if llm_gate:
        return _gate_decision_from_llm(llm_gate, waiting, recent, resolved)

    return _fallback_gate_decision(normalized, waiting, recent, workspace, chat_session)


async def route_intent(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    content: str,
    *,
    previous_turn: IntentTurn | None = None,
    gate_context: dict[str, Any] | None = None,
    open_file_context: dict[str, Any] | None = None,
    open_mail_context: dict[str, Any] | None = None,
) -> RouterDecision:
    resolved = await build_resolved_intent_context(
        db,
        project,
        chat_session,
        content,
        previous_turn=previous_turn,
        gate_context=gate_context,
        user_id=project.user_id,
        open_file_context=open_file_context,
        open_mail_context=open_mail_context,
    )

    llm_decision = await llm_route(resolved)
    if llm_decision:
        return apply_file_discovery_constraints(llm_decision, resolved)

    shortcut = rule_route(resolved)
    if shortcut:
        return apply_file_discovery_constraints(shortcut, resolved)

    return apply_file_discovery_constraints(fallback_router_decision(resolved), resolved)


def apply_file_discovery_constraints(route: RouterDecision, resolved: ResolvedIntentContext) -> RouterDecision:
    discovery = resolved.file_discovery_context or {}
    if not discovery.get("source_content_missing"):
        return route
    question = discovery.get("recommended_user_question")
    route.can_execute = False
    route.selected_tools = []
    route.missing_info = sorted(set([*route.missing_info, *discovery.get("missing_info", [])]))
    route.question = str(question or route.question or "추가할 원문 파일의 경로를 알려주세요.")
    route.reason = f"{route.reason} File Discovery Context가 source content 후보를 찾지 못했습니다.".strip()
    return route


def gate_context_payload(gate: GateDecision) -> dict[str, Any]:
    return {
        "decision": gate.decision,
        "reason": gate.reason,
        "source": gate.source,
        "confidence": gate.confidence,
        "artifact_path": gate.artifact_path,
        "artifact_kind": gate.artifact_kind,
        "artifact_url": gate.artifact_url,
        "artifact_action": gate.artifact_action,
        "intent_turn_id": gate.intent_turn.id if gate.intent_turn else None,
    }


async def create_intent_turn(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    user_msg: Message,
    *,
    parent_intent_turn_id: str | None = None,
) -> IntentTurn:
    turn = IntentTurn(
        project_id=project.id,
        chat_session_id=chat_session.id,
        status="routing",
        original_message_id=user_msg.id,
        parent_intent_turn_id=parent_intent_turn_id,
        summary=summarize_text(user_msg.content),
    )
    db.add(turn)
    await db.commit()
    await db.refresh(turn)
    return turn


async def update_intent_turn_from_route(db: AsyncSession, turn: IntentTurn, route: RouterDecision, status: str) -> None:
    current_time = now()
    turn.status = status
    turn.current_intent = route.intent
    turn.confidence = route.confidence
    turn.risk_level = route.risk_level
    turn.selected_tools_json = json.dumps(route.selected_tools, ensure_ascii=False)
    turn.selected_skills_json = json.dumps(route.selected_skills, ensure_ascii=False)
    turn.missing_info_json = json.dumps(route.missing_info, ensure_ascii=False)
    turn.updated_at = current_time
    if status in {"completed", "blocked", "failed", "cancelled", "abandoned"}:
        turn.completed_at = current_time
    await db.commit()


async def set_intent_status(db: AsyncSession, turn: IntentTurn, status: str) -> None:
    current_time = now()
    turn.status = status
    turn.updated_at = current_time
    if status in {"completed", "blocked", "failed", "cancelled", "abandoned"}:
        turn.completed_at = current_time
    await db.commit()


async def record_intent_event(
    db: AsyncSession,
    turn: IntentTurn,
    event_type: str,
    payload: dict[str, Any],
    *,
    message_id: str | None = None,
    debug_payload: dict[str, Any] | None = None,
) -> IntentTurnEvent:
    event = IntentTurnEvent(
        intent_turn_id=turn.id,
        message_id=message_id,
        event_type=event_type,
        payload_json=json.dumps(payload, ensure_ascii=False, default=str),
        debug_payload_json=json.dumps(debug_payload, ensure_ascii=False, default=str) if debug_payload else None,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def get_recent_intent_turns(db: AsyncSession, chat_session_id: str, limit: int = RECENT_INTENT_LIMIT) -> list[IntentTurn]:
    result = await db.execute(
        select(IntentTurn)
        .where(IntentTurn.chat_session_id == chat_session_id)
        .order_by(desc(IntentTurn.updated_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def find_intent_turns_for_message(db: AsyncSession, chat_session_id: str, message_id: str) -> list[IntentTurn]:
    event_turn_ids = (
        select(IntentTurnEvent.intent_turn_id)
        .where(IntentTurnEvent.message_id == message_id)
    )
    result = await db.execute(
        select(IntentTurn)
        .where(
            IntentTurn.chat_session_id == chat_session_id,
            or_(IntentTurn.original_message_id == message_id, IntentTurn.id.in_(event_turn_ids)),
        )
        .order_by(IntentTurn.created_at.asc())
    )
    return list(result.scalars().all())


def selected_tools_from_turn(turn: IntentTurn | None) -> list[str]:
    if not turn:
        return []
    try:
        return normalize_tool_names(json.loads(turn.selected_tools_json))
    except Exception:
        return []


async def _get_waiting_intent(db: AsyncSession, chat_session_id: str) -> IntentTurn | None:
    result = await db.execute(
        select(IntentTurn)
        .where(
            IntentTurn.chat_session_id == chat_session_id,
            IntentTurn.status.in_(["needs_clarification", "waiting_review"]),
        )
        .order_by(desc(IntentTurn.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _gate_decision_from_llm(
    result: LlmGateResult,
    waiting: IntentTurn | None,
    recent: list[IntentTurn],
    resolved: ResolvedIntentContext,
) -> GateDecision:
    candidates = reference_candidates(recent)
    by_id = {turn.id: turn for turn in recent}
    if waiting:
        by_id[waiting.id] = waiting
    intent_turn = by_id.get(result.intent_turn_id or "")

    decision = result.decision
    if decision == "continue_intent":
        if waiting:
            intent_turn = waiting
        elif intent_turn:
            decision = "revive_intent"
        else:
            decision = "new_task"

    if decision == "cancel_intent" and not waiting:
        decision = "casual_chat"
        intent_turn = None

    if decision == "revive_intent":
        if not intent_turn and len(candidates) == 1:
            intent_turn = candidates[0]
        elif not intent_turn and len(candidates) > 1:
            decision = "ambiguous_reference"

    artifact_path = result.artifact_path or _latest_artifact_path(resolved)
    artifact_url = result.artifact_url or _latest_preview_url(resolved)
    artifact_kind = result.artifact_kind or _latest_artifact_kind(resolved)
    artifact_action = result.artifact_action if decision == "artifact_reference" else None

    if decision == "artifact_reference":
        if not intent_turn and candidates:
            intent_turn = candidates[0]
        if not artifact_path and not artifact_url:
            return GateDecision(
                "missing_artifact_reference",
                "LLM gate가 최근 산출물 참조로 판단했지만 사용할 산출물/프리뷰 정보가 없습니다.",
                intent_turn,
                candidates[:3],
                artifact_action=artifact_action,
                confidence=result.confidence,
                source="llm",
            )

    return GateDecision(
        decision,
        result.reason,
        intent_turn,
        candidates[:3],
        artifact_path=artifact_path if decision == "artifact_reference" else None,
        artifact_kind=artifact_kind if decision == "artifact_reference" else None,
        artifact_url=artifact_url if decision == "artifact_reference" else None,
        artifact_action=artifact_action,
        confidence=result.confidence,
        source="llm",
    )


def _fallback_gate_decision(
    normalized: str,
    waiting: IntentTurn | None,
    recent: list[IntentTurn],
    workspace: str | None,
    chat_session: ChatSession,
) -> GateDecision:
    if waiting:
        if is_cancel(normalized):
            return GateDecision("cancel_intent", "LLM gate 실패 후 fallback: 취소 요청입니다.", waiting, source="fallback")
        return GateDecision("continue_intent", "LLM gate 실패 후 fallback: 진행 중인 질문에 대한 답변으로 처리합니다.", waiting, source="fallback")

    if is_casual_chat(normalized):
        return GateDecision("casual_chat", "LLM gate 실패 후 fallback: 일반 대화입니다.", source="fallback")

    if looks_like_artifact_reference(normalized):
        candidates = reference_candidates(recent)
        artifact = get_latest_chat_output_reference(workspace, chat_session) if workspace else None
        if artifact:
            return GateDecision(
                "artifact_reference",
                "LLM gate 실패 후 fallback: 최근 산출물 참조 요청입니다.",
                candidates[0] if candidates else None,
                candidates[:3],
                artifact_path=artifact.get("path"),
                artifact_kind=artifact.get("kind"),
                artifact_action="unknown",
                source="fallback",
            )
        return GateDecision(
            "missing_artifact_reference",
            "LLM gate 실패 후 fallback: 참조할 최근 산출물이 없습니다.",
            candidates[0] if len(candidates) == 1 else None,
            candidates[:3],
            source="fallback",
        )

    if looks_like_reference(normalized):
        candidates = reference_candidates(recent)
        if len(candidates) == 1:
            return GateDecision("revive_intent", "LLM gate 실패 후 fallback: 최근 작업 후속 요청입니다.", candidates[0], candidates, source="fallback")
        if len(candidates) > 1:
            return GateDecision("ambiguous_reference", "LLM gate 실패 후 fallback: 참조 후보가 여러 개입니다.", None, candidates[:3], source="fallback")

    return GateDecision("new_task", "LLM gate 실패 후 fallback: 업무로 처리해 맥락 손실을 피합니다.", source="fallback")


def _latest_artifact_path(resolved: ResolvedIntentContext) -> str | None:
    artifact = resolved.latest_artifact or {}
    path = artifact.get("path")
    return str(path) if path else None


def _latest_artifact_kind(resolved: ResolvedIntentContext) -> str | None:
    artifact = resolved.latest_artifact or {}
    preview = resolved.latest_preview or {}
    kind = artifact.get("kind") or preview.get("kind")
    return str(kind) if kind else None


def _latest_preview_url(resolved: ResolvedIntentContext) -> str | None:
    preview = resolved.latest_preview or {}
    url = preview.get("url")
    return str(url) if url else None
