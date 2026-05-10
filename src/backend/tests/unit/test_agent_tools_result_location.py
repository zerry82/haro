from __future__ import annotations

import asyncio
from pathlib import Path

from app.models.chat_session import ChatSession
from app.models.project import Project
from app.services import agent_tools
from app.services.agent_tools import execute_tool
from app.services.web_search import WebSearchResult
from app.services.workspace_file_db import list_workspace_directory, sync_workspace_subtree


class _Emitter:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def emit(self, event: str, payload: dict) -> None:
        self.events.append((event, payload))


def _project(workspace: Path) -> Project:
    return Project(id="p1", user_id="u1", title="Project", workspace_path=str(workspace))


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


def test_file_move_merges_directory_and_updates_workspace_index(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source = workspace / "playground" / "users" / "u1" / "30_outputs" / "기업분석"
    target = workspace / "playground" / "users" / "u1" / "30_outputs" / "01_리서치_및_보고서" / "기업_산업"
    source.mkdir(parents=True)
    target.mkdir(parents=True)
    (source / "report.md").write_text("# Report\n", encoding="utf-8")
    sync_workspace_subtree(str(workspace), "/playground/users/u1/30_outputs")

    result = asyncio.run(
        execute_tool(
            str(workspace),
            "file_move",
            {
                "source_path": "내 폴더/결과/기업분석",
                "target_path": "내 폴더/결과/01_리서치_및_보고서/기업_산업",
            },
            _Emitter(),  # type: ignore[arg-type]
            project=_project(workspace),
        )
    )

    assert result.startswith("이동 완료")
    assert not source.exists()
    assert (target / "report.md").exists()
    names = [item["name"] for item in list_workspace_directory(str(workspace), "/playground/users/u1/30_outputs/01_리서치_및_보고서/기업_산업")]
    assert names == ["report.md"]


def test_dir_delete_removes_empty_directory_and_updates_workspace_index(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    empty_dir = workspace / "playground" / "users" / "u1" / "30_outputs" / "empty"
    empty_dir.mkdir(parents=True)
    sync_workspace_subtree(str(workspace), "/playground/users/u1/30_outputs")

    result = asyncio.run(
        execute_tool(
            str(workspace),
            "dir_delete",
            {"path": "내 폴더/결과/empty"},
            _Emitter(),  # type: ignore[arg-type]
            project=_project(workspace),
        )
    )

    assert result == "디렉토리 삭제 완료: /playground/users/u1/30_outputs/empty"
    assert not empty_dir.exists()
    names = [item["name"] for item in list_workspace_directory(str(workspace), "/playground/users/u1/30_outputs")]
    assert "empty" not in names


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


def test_file_stats_tool_resolves_alias_and_emits_measurement(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    report = workspace / "playground" / "users" / "u1" / "30_outputs" / "report.md"
    report.parent.mkdir(parents=True)
    report.write_text("one two\nthree\n", encoding="utf-8")
    emitter = _Emitter()

    result = asyncio.run(
        execute_tool(
            str(workspace),
            "file_stats",
            {"path": "내 폴더/결과/report.md"},
            emitter,  # type: ignore[arg-type]
            project=_project(workspace),
        )
    )

    assert '"path": "/playground/users/u1/30_outputs/report.md"' in result
    assert '"words": 3' in result
    assert any(event == "file_stats_collected" for event, _payload in emitter.events)
    assert any(event == "quantitative_requirement_measured" for event, _payload in emitter.events)


def test_file_edit_tool_modifies_file_and_emits_file_changed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    report = workspace / "playground" / "users" / "u1" / "30_outputs" / "report.md"
    report.parent.mkdir(parents=True)
    report.write_text("hello old world\n", encoding="utf-8")
    emitter = _Emitter()

    result = asyncio.run(
        execute_tool(
            str(workspace),
            "file_edit",
            {
                "path": "내 폴더/결과/report.md",
                "old_string": "old world",
                "new_string": "new world",
            },
            emitter,  # type: ignore[arg-type]
            project=_project(workspace),
        )
    )

    assert result.startswith("파일 부분 수정 완료")
    assert report.read_text(encoding="utf-8") == "hello new world\n"
    assert any(event == "file_edit_completed" for event, _payload in emitter.events)
    assert any(
        event == "file_changed" and payload["action"] == "modified"
        for event, payload in emitter.events
    )


def test_file_edit_tool_blocks_checksum_mismatch_without_writing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    report = workspace / "playground" / "users" / "u1" / "30_outputs" / "report.md"
    report.parent.mkdir(parents=True)
    report.write_text("hello old world\n", encoding="utf-8")
    emitter = _Emitter()

    result = asyncio.run(
        execute_tool(
            str(workspace),
            "file_edit",
            {
                "path": "내 폴더/결과/report.md",
                "old_string": "old world",
                "new_string": "new world",
                "expected_sha256": "bad",
            },
            emitter,  # type: ignore[arg-type]
            project=_project(workspace),
        )
    )

    assert result.startswith("부분 파일 작업 차단")
    assert report.read_text(encoding="utf-8") == "hello old world\n"
    assert any(event == "file_checksum_mismatch" for event, _payload in emitter.events)
