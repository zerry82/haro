from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MailConnection(Base):
    __tablename__ = "mail_connections"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", "provider", name="uq_mail_connection_project_user_provider"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="gmail")
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="needs_oauth")
    token_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    live_status: Mapped[str] = mapped_column(String(40), nullable=False, default="stopped")
    live_poll_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    last_sync_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[str] = mapped_column(String(50), default=_now)
    updated_at: Mapped[str] = mapped_column(String(50), default=_now)


class MailPolicy(Base):
    __tablename__ = "mail_policies"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", "provider", name="uq_mail_policy_project_user_provider"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="gmail")
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    filters_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String(50), default=_now)
    updated_at: Mapped[str] = mapped_column(String(50), default=_now)


class MailAnalysisRun(Base):
    __tablename__ = "mail_analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="gmail")
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    connection_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("mail_connections.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed")
    range_start: Mapped[str] = mapped_column(String(50), nullable=False)
    range_end: Mapped[str] = mapped_column(String(50), nullable=False)
    stats_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    proposed_categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    proposed_filters_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[str] = mapped_column(String(50), default=_now)
    updated_at: Mapped[str] = mapped_column(String(50), default=_now)


class MailThreadStaging(Base):
    __tablename__ = "mail_thread_staging"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("mail_analysis_runs.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    recipients_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    received_at: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    attachments_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    inclusion_decision: Mapped[str] = mapped_column(String(40), nullable=False, default="allowed")
    promoted_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    clean_room_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String(50), default=_now)
    updated_at: Mapped[str] = mapped_column(String(50), default=_now)


class MailStructureTest(Base):
    __tablename__ = "mail_structure_tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="gmail")
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("mail_analysis_runs.id"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    result_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="search")
    rating: Mapped[str] = mapped_column(String(40), nullable=False, default="good")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String(50), default=_now)


class MailImprovementCandidate(Base):
    __tablename__ = "mail_improvement_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="gmail")
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("mail_analysis_runs.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(40), nullable=False, default="medium")
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="user")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open")
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    thread_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String(50), default=_now)
    updated_at: Mapped[str] = mapped_column(String(50), default=_now)
