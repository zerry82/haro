from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from app.models.chat_session import ChatSession
from app.services.harness import normalize_workspace_path
from app.services.workspace_aliases import resolve_workspace_alias_path

CHAT_AREA_ALIASES = {"inputs", "working", "outputs", "summaries"}
WORKSPACE_ROOT_PREFIXES = ("/playground/", "/clean-room/", "/90_archive/", "/.haro/")
RESULT_PATH_REQUIRED_MESSAGE = (
    "저장 위치 확인 필요: 최종 산출물은 `내 폴더/결과/{주제}/{파일명}`처럼 "
    "사용자에게 보이는 경로를 명확히 지정해 주세요. "
    "예: `내 폴더/결과/사마귀의-일생/praying_mantis_essay.html`"
)


class ResultPathRequiredError(ValueError):
    """Raised when a final artifact path would otherwise use an implicit folder."""


def get_chat_default_write_path(
    chat: ChatSession,
    requested: str | None,
    tool_name: str,
    user_id: str | None = None,
) -> str:
    """Resolve implicit write paths for agent tools.

    User-facing file writes default to the user's result folder. Chat workspace
    folders are reserved for temporary execution state and explicit chat paths.
    """
    requested = (requested or "").replace("\\", "/").strip()
    if user_id and _starts_with_workspace_alias(requested):
        return resolve_workspace_alias_path(requested, user_id)
    if is_explicit_workspace_path(requested):
        return normalize_workspace_path(requested)

    name = requested.lstrip("/") or ("new-folder" if tool_name == "dir_create" else "output.md")
    parts = [part for part in name.split("/") if part]
    if user_id and tool_name in {"file_create", "file_write"}:
        if len(parts) <= 1 or (parts and parts[0] in CHAT_AREA_ALIASES):
            raise ResultPathRequiredError(RESULT_PATH_REQUIRED_MESSAGE)
        safe_name = "/".join(safe_segment(part, "untitled") for part in parts)
        return normalize_workspace_path(f"{user_result_root_path(user_id)}/{safe_name}")

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


def user_result_root_path(user_id: str) -> str:
    return f"/playground/users/{user_id}/30_outputs"


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


def _starts_with_workspace_alias(path: str) -> bool:
    alias_path = path.replace("\\", "/").strip().strip("/")
    return alias_path == "내 폴더" or alias_path == "팀 폴더" or alias_path.startswith(("내 폴더/", "팀 폴더/"))


def full_path(workspace: str, requested: str) -> str:
    normalized = normalize_workspace_path(requested)
    workspace_real = os.path.realpath(workspace)
    full = os.path.realpath(os.path.join(workspace_real, normalized.lstrip("/")))
    if os.path.commonpath([workspace_real, full]) != workspace_real:
        raise PermissionError("워크스페이스 외부 접근 불가")
    return full
