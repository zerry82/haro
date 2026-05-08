from __future__ import annotations

from pathlib import Path

from app.models.chat_session import ChatSession
from app.services.chat_workspace_paths import (
    ResultPathRequiredError,
    default_chat_folder_path,
    full_path,
    get_chat_default_write_path,
    safe_segment,
    user_result_root_path,
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
    assert user_result_root_path("user-1") == "/playground/users/user-1/30_outputs"


def test_default_write_path_keeps_explicit_workspace_paths() -> None:
    chat = _chat()

    assert get_chat_default_write_path(chat, "/clean-room/data/source.csv", "file_write") == "/clean-room/data/source.csv"
    assert get_chat_default_write_path(chat, "내 폴더/결과/report.md", "file_create", "u") == (
        "/playground/users/u/30_outputs/report.md"
    )
    assert get_chat_default_write_path(chat, "사마귀의-일생/report.md", "file_create", "u") == (
        "/playground/users/u/30_outputs/사마귀의-일생/report.md"
    )
    assert get_chat_default_write_path(chat, "outputs/report.md", "file_write") == (
        "/playground/users/u/50_chats/chat/outputs/report.md"
    )
    assert get_chat_default_write_path(chat, None, "dir_create") == (
        "/playground/users/u/50_chats/chat/working/new-folder"
    )


def test_user_result_writes_require_clear_location_for_bare_or_chat_area_paths() -> None:
    chat = _chat()

    for path in ["notes.md", "outputs/report.md", "working/report.md", None]:
        try:
            get_chat_default_write_path(chat, path, "file_create", "u")
        except ResultPathRequiredError as exc:
            assert "저장 위치 확인 필요" in str(exc)
            assert "내 폴더/결과/{주제}/{파일명}" in str(exc)
        else:
            raise AssertionError(f"expected ResultPathRequiredError for {path!r}")


def test_full_path_normalizes_relative_traversal_inside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    assert full_path(str(workspace), "../outside.txt") == str((workspace / "outside.txt").resolve())
