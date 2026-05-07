from __future__ import annotations

import contextlib
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Iterator

from app.services.workspace_file_helpers import META_DIR, db_path

_PROCESS_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def connect(workspace: str) -> sqlite3.Connection:
    path = db_path(workspace)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=DELETE")
    return conn


def atomic_write_text(path: str, content: str) -> None:
    atomic_write_bytes(path, content.encode("utf-8"))


def atomic_write_bytes(path: str, content: bytes) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temp_path = os.path.join(directory, f".{os.path.basename(path)}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temp_path, "wb") as f:
            f.write(content)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            with contextlib.suppress(OSError):
                os.remove(temp_path)


@contextlib.contextmanager
def workspace_writer_lock(workspace: str) -> Iterator[None]:
    workspace_real = os.path.realpath(workspace)
    process_lock = _get_process_lock(workspace_real)
    with process_lock:
        os.makedirs(os.path.join(workspace_real, META_DIR, "locks"), exist_ok=True)
        lock_path = os.path.join(workspace_real, META_DIR, "locks", "workspace-db.lock")
        with open(lock_path, "a+b") as lock_file:
            _lock_file(lock_file)
            try:
                yield
            finally:
                _unlock_file(lock_file)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_process_lock(workspace: str) -> threading.RLock:
    with _PROCESS_LOCKS_GUARD:
        lock = _PROCESS_LOCKS.get(workspace)
        if lock is None:
            lock = threading.RLock()
            _PROCESS_LOCKS[workspace] = lock
        return lock


def _lock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _unlock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt
        lock_file.seek(0)
        with contextlib.suppress(OSError):
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
