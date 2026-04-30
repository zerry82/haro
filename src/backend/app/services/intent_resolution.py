from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.intent_turn import IntentTurn, IntentTurnEvent
from app.models.message import Message
from app.models.project import Project
from app.services.chat_workspace import get_latest_chat_output_reference, get_latest_chat_preview_reference
from app.services.tool_registry import normalize_tool_names


@dataclass
class ResolvedIntentContext:
    current_message: str
    routing_text: str
    chat_workspace: str | None
    gate_context: dict[str, Any] | None
    is_clarification_answer: bool
    previous_intent: dict[str, Any] | None
    clarification_question: str | None
    latest_artifact: dict[str, Any] | None
    latest_preview: dict[str, Any] | None
    latest_assistant_message: str | None
    recent_messages: list[dict[str, Any]]
    recent_intents: list[dict[str, Any]]

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "current_user_message": self.current_message,
            "routing_text": self.routing_text,
            "chat_workspace": self.chat_workspace,
            "gate_context": self.gate_context,
            "is_clarification_answer": self.is_clarification_answer,
            "previous_intent": self.previous_intent,
            "clarification_question": self.clarification_question,
            "latest_artifact": self.latest_artifact,
            "latest_preview": self.latest_preview,
            "latest_assistant_message": self.latest_assistant_message,
            "recent_messages": self.recent_messages,
            "recent_intents": self.recent_intents,
        }


async def build_resolved_intent_context(
    db: AsyncSession,
    project: Project | None,
    chat_session: ChatSession,
    content: str,
    *,
    workspace: str | None = None,
    previous_turn: IntentTurn | None = None,
    recent_turns: list[IntentTurn] | None = None,
    gate_context: dict[str, Any] | None = None,
) -> ResolvedIntentContext:
    workspace_path = workspace or (project.workspace_path if project else None)
    previous_message = await _previous_user_message(db, previous_turn)
    clarification_question = await _latest_clarification_question(db, previous_turn)
    latest_artifact = get_latest_chat_output_reference(workspace_path, chat_session) if workspace_path else None
    latest_preview = get_latest_chat_preview_reference(workspace_path, chat_session) if workspace_path else None
    recent_messages = await _recent_messages(db, chat_session.id)
    latest_assistant_message = _latest_assistant_text(recent_messages)
    recent_intents = _recent_intent_payloads(recent_turns or await _recent_intent_turns(db, chat_session.id))
    is_clarification_answer = bool(previous_turn and previous_turn.status in {"needs_clarification", "waiting_review"})

    previous_intent = _previous_intent_payload(previous_turn, previous_message)
    routing_text = _build_routing_text(
        content,
        previous_message=previous_message,
        clarification_question=clarification_question,
        is_clarification_answer=is_clarification_answer,
    )

    return ResolvedIntentContext(
        current_message=content,
        routing_text=routing_text,
        chat_workspace=chat_session.folder_path,
        gate_context=gate_context,
        is_clarification_answer=is_clarification_answer,
        previous_intent=previous_intent,
        clarification_question=clarification_question,
        latest_artifact=latest_artifact,
        latest_preview=latest_preview,
        latest_assistant_message=latest_assistant_message,
        recent_messages=recent_messages,
        recent_intents=recent_intents,
    )


async def _previous_user_message(db: AsyncSession, previous_turn: IntentTurn | None) -> str | None:
    if not previous_turn or not previous_turn.original_message_id:
        return None
    result = await db.execute(select(Message).where(Message.id == previous_turn.original_message_id))
    message = result.scalar_one_or_none()
    return message.content if message else None


async def _latest_clarification_question(db: AsyncSession, previous_turn: IntentTurn | None) -> str | None:
    if not previous_turn:
        return None
    result = await db.execute(
        select(IntentTurnEvent)
        .where(
            IntentTurnEvent.intent_turn_id == previous_turn.id,
            IntentTurnEvent.event_type == "clarification_question",
        )
        .order_by(desc(IntentTurnEvent.created_at))
        .limit(1)
    )
    event = result.scalar_one_or_none()
    if not event:
        return None
    try:
        payload = json.loads(event.payload_json)
    except Exception:
        return None
    question = payload.get("question")
    return str(question) if question else None


def _previous_intent_payload(previous_turn: IntentTurn | None, previous_message: str | None) -> dict[str, Any] | None:
    if not previous_turn:
        return None
    return {
        "id": previous_turn.id,
        "status": previous_turn.status,
        "intent": previous_turn.current_intent,
        "summary": previous_turn.summary,
        "original_user_message": previous_message,
        "selected_tools": _selected_tools(previous_turn),
        "missing_info": _json_list(previous_turn.missing_info_json),
    }


async def _recent_messages(db: AsyncSession, chat_session_id: str, limit: int = 8) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Message)
        .where(Message.chat_session_id == chat_session_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return [
        {
            "id": message.id,
            "role": message.role,
            "content": _truncate(message.content, 600),
            "created_at": message.created_at,
        }
        for message in messages
    ]


def _latest_assistant_text(messages: list[dict[str, Any]]) -> str | None:
    for message in reversed(messages):
        if message.get("role") != "user":
            content = message.get("content")
            return str(content) if content else None
    return None


async def _recent_intent_turns(db: AsyncSession, chat_session_id: str, limit: int = 5) -> list[IntentTurn]:
    result = await db.execute(
        select(IntentTurn)
        .where(IntentTurn.chat_session_id == chat_session_id)
        .order_by(desc(IntentTurn.updated_at))
        .limit(limit)
    )
    return list(result.scalars().all())


def _recent_intent_payloads(turns: list[IntentTurn]) -> list[dict[str, Any]]:
    return [
        {
            "id": turn.id,
            "status": turn.status,
            "intent": turn.current_intent,
            "summary": turn.summary,
            "selected_tools": _selected_tools(turn),
            "missing_info": _json_list(turn.missing_info_json),
            "updated_at": turn.updated_at,
        }
        for turn in turns
        if not (turn.status == "routing" and not turn.current_intent)
    ]


def _build_routing_text(
    content: str,
    *,
    previous_message: str | None,
    clarification_question: str | None,
    is_clarification_answer: bool,
) -> str:
    if not is_clarification_answer:
        return content
    parts = []
    if previous_message:
        parts.append(f"이전 사용자 요청: {previous_message}")
    if clarification_question:
        parts.append(f"에이전트 확인 질문: {clarification_question}")
    parts.append(f"현재 사용자 답변: {content}")
    return "\n".join(parts)


def _selected_tools(turn: IntentTurn) -> list[str]:
    try:
        return normalize_tool_names(json.loads(turn.selected_tools_json))
    except Exception:
        return []


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except Exception:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def _truncate(text: str, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."
