from __future__ import annotations

import os

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    global engine, async_session_factory
    os.makedirs(os.path.dirname(settings.db_data_dir) or ".", exist_ok=True)

    os.makedirs(settings.db_data_dir, exist_ok=True)
    db_path = os.path.join(settings.db_data_dir, "haro.db")
    legacy_db_path = os.path.join(settings.db_data_dir, "openclaw.db")
    if not os.path.exists(db_path) and os.path.exists(legacy_db_path):
        db_path = legacy_db_path
    async_url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_async_engine(async_url, echo=False)

    # SQLite에서 FK 지원 활성화
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    print(f"[DB] SQLite: {db_path}")
