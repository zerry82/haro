from __future__ import annotations

from pathlib import Path

from app.models.chat_session import ChatSession
from app.services.chat_workspace_paths import (
    default_chat_folder_path,
    full_path,
    get_chat_default_write_path,
    safe_segment,
)


def _chat(folder_path: str | None = "/playground/users/u/50_chats/chat") -> ChatSession:
    return ChatSession(
        id="chat-12345678",
        project_id="project-1",
        title="Design Notes",
        folder_path=folder_path,
        created_at="2026-05-07T00:00:00+00:00",
        updated_at="2026-05-07T00:00:00+00:00",
    )


def test_safe_segment_and_default_folder_path_are_stable() -> None:
    chat = _chat(folder_path=None)

    assert safe_segment("  My / Unsafe: Chat  ", "chat") == "my-unsafe-chat"
    assert default_chat_folder_path("user-1", chat) == (
        "/playground/users/user-1/50_chats/2026-05-07-design-notes-chat-123"
    )


def test_default_write_path_keeps_explicit_workspace_paths() -> None:
    chat = _chat()

    assert get_chat_default_write_path(chat, "/clean-room/data/source.csv", "file_write") == "/clean-room/data/source.csv"
    assert get_chat_default_write_path(chat, "outputs/report.md", "file_write") == (
        "/playground/users/u/50_chats/chat/outputs/report.md"
    )
    assert get_chat_default_write_path(chat, "notes.md", "file_write") == (
        "/playground/users/u/50_chats/chat/outputs/notes.md"
    )
    assert get_chat_default_write_path(chat, None, "dir_create") == (
        "/playground/users/u/50_chats/chat/working/new-folder"
    )


def test_full_path_normalizes_relative_traversal_inside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    assert full_path(str(workspace), "../outside.txt") == str((workspace / "outside.txt").resolve())
