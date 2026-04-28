from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.database as db_module
from app.dependencies import get_current_user, get_db
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.project import Project
from app.models.user import User
from app.services.agent import run_agent
from app.services.sse import SSEEmitter

router = APIRouter(
    prefix="/api/projects/{project_id}/chats/{chat_id}/messages",
    tags=["messages"],
)


class SendMessageRequest(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    metadata: dict | None = None
    created_at: str


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]


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
                created_at=m.created_at,
            )
            for m in msgs
        ]
    )


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
    emitter = SSEEmitter()

    async def _run():
        async with db_module.async_session_factory() as agent_db:
            result = await agent_db.execute(
                select(ChatSession).where(ChatSession.id == chat_id_val)
            )
            agent_chat = result.scalar_one()
            result = await agent_db.execute(
                select(Project).where(Project.id == project_id_val)
            )
            agent_project = result.scalar_one()
            await run_agent(agent_db, agent_chat, agent_project, content, emitter)

    asyncio.create_task(_run())

    return StreamingResponse(
        emitter.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
