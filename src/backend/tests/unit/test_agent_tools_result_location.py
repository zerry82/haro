from __future__ import annotations

import asyncio
from pathlib import Path

from app.models.chat_session import ChatSession
from app.models.project import Project
from app.services.agent_tools import execute_tool


class _Emitter:
    def emit(self, event: str, payload: dict) -> None:
        pass


def test_file_create_with_bare_filename_asks_for_result_location(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = Project(id="p1", user_id="u1", title="Project", workspace_path=str(workspace))
    chat = ChatSession(
        id="chat-12345678",
        project_id="p1",
        title="New Chat",
        folder_path="/playground/users/u1/50_chats/2026-05-07-new-chat-chat-123",
    )

    result = asyncio.run(
        execute_tool(
            str(workspace),
            "file_create",
            {"path": "report.html", "content": "<html></html>"},
            _Emitter(),  # type: ignore[arg-type]
            project=project,
            chat_session=chat,
        )
    )

    assert result.startswith("저장 위치 확인 필요")
    assert "도구 실행 에러" not in result
    assert not (workspace / "playground").exists()
