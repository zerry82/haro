from __future__ import annotations

from datetime import datetime, timezone

from app.models.chat_session import ChatSession
from app.services.chat_workspace_files import append_text


def append_conversation_message(
    workspace: str,
    chat: ChatSession,
    role: str,
    content: str,
    created_at: str | None = None,
) -> None:
    if not chat.folder_path:
        return
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    label = "사용자" if role == "user" else "haro"
    entry = f"## {timestamp} {label}\n\n{content.strip()}\n\n"
    append_text(workspace, chat.folder_path, "conversation.md", entry)


def append_agent_log(workspace: str, chat: ChatSession, event_type: str, content: str) -> None:
    if not chat.folder_path:
        return
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"## {timestamp} {event_type}\n\n```text\n{content.strip()}\n```\n\n"
    append_text(workspace, chat.folder_path, "agent-log.md", entry)
