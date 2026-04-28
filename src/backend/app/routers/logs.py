from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.project import Project
from app.models.user import User

router = APIRouter(prefix="/api/projects/{project_id}/chats/{chat_id}/logs", tags=["logs"])


class LogEntry(BaseModel):
    id: str
    round_index: int
    event_type: str
    content: str
    duration_ms: float | None
    created_at: str


class LogListResponse(BaseModel):
    logs: list[LogEntry]


@router.get("", response_model=LogListResponse)
async def get_chat_logs(
    project_id: str,
    chat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        return LogListResponse(logs=[])

    # Verify chat belongs to project
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == chat_id, ChatSession.project_id == project_id)
    )
    if not result.scalar_one_or_none():
        return LogListResponse(logs=[])

    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.chat_session_id == chat_id)
        .order_by(AgentLog.created_at.asc())
    )
    logs = result.scalars().all()
    return LogListResponse(
        logs=[
            LogEntry(
                id=l.id, round_index=l.round_index, event_type=l.event_type,
                content=l.content, duration_ms=l.duration_ms, created_at=l.created_at,
            )
            for l in logs
        ]
    )
