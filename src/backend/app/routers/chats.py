from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.project import Project
from app.models.user import User

router = APIRouter(prefix="/api/projects/{project_id}/chats", tags=["chats"])


class CreateChatRequest(BaseModel):
    title: str = "새 채팅"


class UpdateChatRequest(BaseModel):
    title: str


class ChatSessionResponse(BaseModel):
    id: str
    project_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ChatSessionListResponse(BaseModel):
    chats: list[ChatSessionResponse]


async def _get_user_project(db: AsyncSession, user_id: str, project_id: str) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _get_chat_session(db: AsyncSession, project_id: str, chat_id: str) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == chat_id, ChatSession.project_id == project_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat


@router.get("", response_model=ChatSessionListResponse)
async def list_chats(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(db, user.id, project_id)

    stmt = (
        select(ChatSession, func.count(Message.id).label("msg_count"))
        .outerjoin(Message, Message.chat_session_id == ChatSession.id)
        .where(ChatSession.project_id == project_id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return ChatSessionListResponse(
        chats=[
            ChatSessionResponse(
                id=c.id, project_id=c.project_id, title=c.title,
                created_at=c.created_at, updated_at=c.updated_at,
                message_count=cnt,
            )
            for c, cnt in rows
        ]
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ChatSessionResponse)
async def create_chat(
    project_id: str,
    body: CreateChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    chat = ChatSession(project_id=project.id, title=body.title)
    db.add(chat)

    # Update project updated_at
    project.updated_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    await db.refresh(chat)

    return ChatSessionResponse(
        id=chat.id, project_id=chat.project_id, title=chat.title,
        created_at=chat.created_at, updated_at=chat.updated_at,
        message_count=0,
    )


@router.patch("/{chat_id}", response_model=ChatSessionResponse)
async def update_chat(
    project_id: str,
    chat_id: str,
    body: UpdateChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(db, user.id, project_id)
    chat = await _get_chat_session(db, project_id, chat_id)
    chat.title = body.title
    chat.updated_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    await db.refresh(chat)

    result = await db.execute(
        select(func.count(Message.id)).where(Message.chat_session_id == chat.id)
    )
    msg_count = result.scalar() or 0

    return ChatSessionResponse(
        id=chat.id, project_id=chat.project_id, title=chat.title,
        created_at=chat.created_at, updated_at=chat.updated_at,
        message_count=msg_count,
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    project_id: str,
    chat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(db, user.id, project_id)
    chat = await _get_chat_session(db, project_id, chat_id)

    # Check minimum chat constraint
    result = await db.execute(
        select(func.count(ChatSession.id)).where(ChatSession.project_id == project_id)
    )
    chat_count = result.scalar() or 0
    if chat_count <= 1:
        raise HTTPException(
            status_code=400,
            detail="프로젝트에는 최소 하나의 채팅이 있어야 합니다"
        )

    # Delete agent logs and messages for this chat
    await db.execute(delete(AgentLog).where(AgentLog.chat_session_id == chat.id))
    await db.execute(delete(Message).where(Message.chat_session_id == chat.id))
    await db.delete(chat)
    await db.commit()
