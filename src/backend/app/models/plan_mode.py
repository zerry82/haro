from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlanSession(Base):
    __tablename__ = "plan_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chat_session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    original_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    intent_turn_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="plan_drafting", index=True)
    trigger_source: Mapped[str] = mapped_column(String(40), nullable=False, default="user_explicit")
    plan_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    plan_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rejected_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[str] = mapped_column(String(50), default=_now)
    updated_at: Mapped[str] = mapped_column(String(50), default=_now)
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)


class PlanEvent(Base):
    __tablename__ = "plan_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("plan_sessions.id"), nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(50), default=_now)


class ExecutionTodo(Base):
    __tablename__ = "execution_todos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("plan_sessions.id"), nullable=False, index=True)
    intent_turn_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    verification: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(50), default=_now)
    updated_at: Mapped[str] = mapped_column(String(50), default=_now)
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
