from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="idle")
    workspace_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.now(timezone.utc).isoformat())

    # Sandbox fields
    sandbox_node_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sandbox_nodes.id"), nullable=True)
    container_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    container_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")  # "none"|"creating"|"running"|"stopped"|"error"
    last_activity_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
