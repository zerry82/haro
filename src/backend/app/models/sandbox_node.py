from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SandboxNode(Base):
    __tablename__ = "sandbox_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    host: Mapped[str] = mapped_column(String(500), nullable=False)  # e.g. "unix:///var/run/docker.sock" or "tcp://10.0.1.5:2376"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # "active" | "draining" | "offline"
    max_containers: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    current_containers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.now(timezone.utc).isoformat())
