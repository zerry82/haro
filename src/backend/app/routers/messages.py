from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.database as db_module
from app.dependencies import get_current_user, get_db
from app.models.agent_debug_trace import AgentDebugTrace
from app.models.chat_session import ChatSession
from app.models.intent_turn import IntentTurnEvent
from app.models.message import Message
from app.models.project import Project
from app.models.user import User
from app.services.intent_turns import find_intent_turns_for_message
from app.services.agent import run_agent
from app.services.sse import SSEEmitter

router = APIRouter(
    prefix="/api/projects/{project_id}/chats/{chat_id}/messages",
    tags=["messages"],
)


class SendMessageRequest(BaseModel):
    content: str
    debug_enabled: bool = False
    client_message_id: str | None = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    metadata: dict | None = None
    created_at: str


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]


class DebugTraceEventResponse(BaseModel):
    id: str
    round_index: int
    event_type: str
    payload: Any
    duration_ms: float | None
    created_at: str


def _message_metadata(message: Message) -> dict | None:
    if not message.metadata_json:
        return None
    try:
        return json.loads(message.metadata_json)
    except Exception:
        return None


class DebugTraceResponse(BaseModel):
    message_id: str
    has_trace: bool
    events: list[DebugTraceEventResponse]


async def _get_project_and_chat(
    db: AsyncSession, user_id: str, project_id: str, chat_id: str
) -> tuple[Project, ChatSession]:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(ChatSession).where(ChatSession.id == chat_id, ChatSession.project_id == project_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    return project, chat


@router.get("", response_model=MessageListResponse)
async def list_messages(
    project_id: str,
    chat_id: str,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, chat = await _get_project_and_chat(db, user.id, project_id, chat_id)
    stmt = (
        select(Message)
        .where(Message.chat_session_id == chat.id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    msgs = result.scalars().all()
    return MessageListResponse(
        messages=[
            MessageResponse(
                id=m.id, role=m.role, content=m.content,
                metadata=_message_metadata(m),
                created_at=m.created_at,
            )
            for m in msgs
        ]
    )


@router.get("/{message_id}/debug-trace", response_model=DebugTraceResponse)
async def get_message_debug_trace(
    project_id: str,
    chat_id: str,
    message_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, chat = await _get_project_and_chat(db, user.id, project_id, chat_id)
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.chat_session_id == chat.id,
            Message.role == "user",
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    events: list[DebugTraceEventResponse] = []
    intent_turns = await find_intent_turns_for_message(db, chat.id, message_id)
    if intent_turns:
        result = await db.execute(
            select(IntentTurnEvent)
            .where(IntentTurnEvent.intent_turn_id.in_([turn.id for turn in intent_turns]))
            .order_by(IntentTurnEvent.created_at.asc())
        )
        for index, event in enumerate(result.scalars().all()):
            raw_payload = event.debug_payload_json or event.payload_json
            try:
                payload = json.loads(raw_payload)
            except Exception:
                payload = raw_payload
            events.append(DebugTraceEventResponse(
                id=event.id,
                round_index=-100 + index,
                event_type=event.event_type,
                payload=payload,
                duration_ms=None,
                created_at=event.created_at,
            ))

    result = await db.execute(
        select(AgentDebugTrace)
        .where(
            AgentDebugTrace.project_id == project_id,
            AgentDebugTrace.chat_session_id == chat.id,
            AgentDebugTrace.turn_message_id == message_id,
        )
        .order_by(AgentDebugTrace.round_index.asc(), AgentDebugTrace.created_at.asc())
    )
    traces = result.scalars().all()
    for trace in traces:
        try:
            payload = json.loads(trace.payload_json)
        except Exception:
            payload = trace.payload_json
        events.append(DebugTraceEventResponse(
            id=trace.id,
            round_index=trace.round_index,
            event_type=trace.event_type,
            payload=payload,
            duration_ms=trace.duration_ms,
            created_at=trace.created_at,
        ))
    return DebugTraceResponse(message_id=message_id, has_trace=bool(events), events=events)


@router.post("")
async def send_message(
    project_id: str,
    chat_id: str,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project, chat = await _get_project_and_chat(db, user.id, project_id, chat_id)
    chat_id_val = chat.id
    project_id_val = project.id
    content = body.content
    debug_enabled = body.debug_enabled
    client_message_id = body.client_message_id
    emitter = SSEEmitter()

    async def _run():
        try:
            async with db_module.async_session_factory() as agent_db:
                result = await agent_db.execute(
                    select(ChatSession).where(ChatSession.id == chat_id_val)
                )
                agent_chat = result.scalar_one()
                result = await agent_db.execute(
                    select(Project).where(Project.id == project_id_val)
                )
                agent_project = result.scalar_one()
                await run_agent(
                    agent_db,
                    agent_chat,
                    agent_project,
                    content,
                    emitter,
                    debug_enabled=debug_enabled,
                    client_message_id=client_message_id,
                )
        except Exception:
            emitter.emit("error", {
                "code": "AGENT_TASK_ERROR",
                "message": "에이전트 실행을 시작하는 중 오류가 발생했습니다.",
            })
            emitter.done()

    asyncio.create_task(_run())

    return StreamingResponse(
        emitter.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
