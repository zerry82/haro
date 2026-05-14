from __future__ import annotations

import asyncio
from types import SimpleNamespace

import app.services.agent_tools as agent_tools
from app.services.agent_tools import execute_tool
from app.services.mail_vector_index import MailVectorSearchUnavailable


class FakeEmitter:
    def emit(self, _event: str, _data) -> None:
        pass


def test_execute_tool_calls_mail_search(monkeypatch) -> None:
    captured = {}

    async def fake_search_mail_analysis(*_args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            query=kwargs["query"],
            run=SimpleNamespace(
                id="run-1",
                status="completed",
                range_start="latest:50",
                range_end="2026-05-12T00:00:00+00:00",
            ),
            items=[{"thread_id": "thread-1", "subject": "카카오 메일"}],
        )

    monkeypatch.setattr(agent_tools, "search_mail_analysis", fake_search_mail_analysis)

    result = asyncio.run(execute_tool(
        "workspace",
        "mail_search",
        {"query": "카카오에서 온 메일들 요약해줘", "limit": 5},
        FakeEmitter(),
        db=SimpleNamespace(),
        project=SimpleNamespace(id="project-1", user_id="user-1"),
        chat_session=SimpleNamespace(id="chat-1"),
    ))

    assert captured["project_id"] == "project-1"
    assert captured["user_id"] == "user-1"
    assert captured["run_id"] == "latest"
    assert captured["limit"] == 5
    assert "카카오 메일" in result


def test_execute_tool_reports_mail_vector_search_unavailable(monkeypatch) -> None:
    async def fake_search_mail_analysis(*_args, **_kwargs):
        raise MailVectorSearchUnavailable("GEMINI_API_KEY is required")

    monkeypatch.setattr(agent_tools, "search_mail_analysis", fake_search_mail_analysis)

    result = asyncio.run(execute_tool(
        "workspace",
        "mail_search",
        {"query": "카카오에서 온 메일들 요약해줘"},
        FakeEmitter(),
        db=SimpleNamespace(),
        project=SimpleNamespace(id="project-1", user_id="user-1", workspace_path="workspace"),
        chat_session=SimpleNamespace(id="chat-1"),
    ))

    assert "메일 벡터 검색을 사용할 수 없습니다" in result
    assert "GEMINI_API_KEY is required" in result
