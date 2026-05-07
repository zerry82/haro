from __future__ import annotations

from pathlib import Path

from app.models.chat_session import ChatSession
from app.models.message import Message
from app.services.chat_workspace_summary import (
    build_context_markdown,
    build_summary_markdown,
    is_summary_suggested,
)


def _chat() -> ChatSession:
    return ChatSession(
        id="chat-1",
        project_id="project-1",
        title="Chat",
        folder_path="/playground/users/u/50_chats/chat",
        created_at="2026-05-07T00:00:00+00:00",
        updated_at="2026-05-07T00:00:00+00:00",
    )


def test_summary_threshold_is_explicit() -> None:
    assert is_summary_suggested(39) is False
    assert is_summary_suggested(40) is True


def test_build_summary_markdown_compacts_message_text() -> None:
    message = Message(
        chat_session_id="chat-1",
        role="user",
        content=("hello\n" * 100),
        created_at="2026-05-07T00:00:00+00:00",
    )

    summary = build_summary_markdown(_chat(), [message], 1, "2026-05-07T01:00:00+00:00")

    assert "# Chat Summary 0001" in summary
    assert "사용자" in summary
    assert "..." in summary


def test_build_context_markdown_includes_recent_summary_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    summary = workspace / "playground" / "users" / "u" / "50_chats" / "chat" / "summaries" / "summary-0001.md"
    summary.parent.mkdir(parents=True)
    summary.write_text("# Summary\n", encoding="utf-8")

    context = build_context_markdown(
        _chat(),
        [{"path": "/playground/users/u/50_chats/chat/summaries/summary-0001.md"}],
        str(workspace),
    )

    assert "# Current Chat Context" in context
    assert "# Summary" in context
