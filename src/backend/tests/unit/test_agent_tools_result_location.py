from __future__ import annotations

import asyncio
from pathlib import Path

from app.models.chat_session import ChatSession
from app.models.project import Project
from app.services import agent_tools
from app.services.agent_tools import execute_tool
from app.services.web_search import WebSearchResult


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


def test_web_search_tool_formats_results(monkeypatch, tmp_path: Path) -> None:
    async def fake_search_web(query, **kwargs):
        assert query == "청개구리 최신 연구"
        assert kwargs["limit"] == 2
        return [
            WebSearchResult(
                title="청개구리 연구",
                url="https://example.com/frog",
                snippet="분포와 개체수 연구",
                source="searxng",
                published_at="2026-05-09",
            )
        ]

    monkeypatch.setattr(agent_tools, "search_web", fake_search_web)

    result = asyncio.run(
        execute_tool(
            str(tmp_path),
            "web_search",
            {"query": "청개구리 최신 연구", "limit": 2},
            _Emitter(),  # type: ignore[arg-type]
        )
    )

    assert "웹 검색 결과 (청개구리 최신 연구):" in result
    assert "URL: https://example.com/frog" in result
    assert "요약: 분포와 개체수 연구" in result


def test_web_search_tool_validates_query(tmp_path: Path) -> None:
    result = asyncio.run(
        execute_tool(
            str(tmp_path),
            "web_search",
            {"query": "   "},
            _Emitter(),  # type: ignore[arg-type]
        )
    )

    assert result == "웹 검색을 실행할 수 없습니다: query가 비어 있습니다."
