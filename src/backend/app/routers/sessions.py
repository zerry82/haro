from __future__ import annotations

import logging
import os
import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.message import Message
from app.models.session import Session
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: str = "새 작업"


class UpdateSessionRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: str
    title: str
    status: str
    container_status: str = "none"
    created_at: str
    updated_at: str
    message_count: int = 0


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


@router.get("", response_model=SessionListResponse)
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Legacy endpoint — returns sessions list for backward compatibility."""
    stmt = (
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.updated_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=s.id, title=s.title, status=s.status,
                container_status=s.container_status,
                created_at=s.created_at, updated_at=s.updated_at,
                message_count=0,
            )
            for s in rows
        ]
    )


async def _get_user_session(db: AsyncSession, user_id: str, session_id: str) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id, Session.user_id == user_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
