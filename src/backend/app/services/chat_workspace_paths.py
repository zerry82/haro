from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from app.models.chat_session import ChatSession
from app.services.harness import normalize_workspace_path

CHAT_AREA_ALIASES = {"inputs", "working", "outputs", "summaries"}
WORKSPACE_ROOT_PREFIXES = ("/playground/", "/clean-room/", "/90_archive/", "/.haro/")


def get_chat_default_write_path(chat: ChatSession, requested: str | None, tool_name: str) -> str:
    """Resolve implicit write paths into the current chat workspace."""
    requested = (requested or "").replace("\\", "/").strip()
    if is_explicit_workspace_path(requested):
        return normalize_workspace_path(requested)

    name = requested.lstrip("/") or ("new-folder" if tool_name == "dir_create" else "output.md")
    parts = [part for part in name.split("/") if part]
    if len(parts) > 1 and parts[0] in CHAT_AREA_ALIASES:
        area = parts[0]
        safe_name = "/".join(safe_segment(part, "untitled") for part in parts[1:])
        return normalize_workspace_path(f"{chat.folder_path}/{area}/{safe_name}")

    safe_name = "/".join(safe_segment(part, "untitled") for part in parts)
    area = "working" if tool_name == "dir_create" else "outputs"
    return normalize_workspace_path(f"{chat.folder_path}/{area}/{safe_name}")


def default_chat_folder_path(user_id: str, chat: ChatSession) -> str:
    date = (chat.created_at or datetime.now(timezone.utc).isoformat())[:10]
    slug = safe_segment(chat.title, "chat")
    return f"/playground/users/{user_id}/50_chats/{date}-{slug}-{chat.id[:8]}"


def safe_segment(value: str | None, fallback: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip(" .-")
    return (value or fallback)[:80]


def is_explicit_workspace_path(path: str) -> bool:
    normalized = normalize_workspace_path(path)
    if not normalized.startswith("/"):
        return False
    return any(normalized.startswith(prefix) for prefix in WORKSPACE_ROOT_PREFIXES)


def full_path(workspace: str, requested: str) -> str:
    normalized = normalize_workspace_path(requested)
    workspace_real = os.path.realpath(workspace)
    full = os.path.realpath(os.path.join(workspace_real, normalized.lstrip("/")))
    if os.path.commonpath([workspace_real, full]) != workspace_real:
        raise PermissionError("워크스페이스 외부 접근 불가")
    return full
