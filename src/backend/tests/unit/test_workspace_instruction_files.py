from __future__ import annotations

import asyncio
from pathlib import Path

from app.models.chat_session import ChatSession
from app.models.project import Project
from app.services.context import build_context
from app.services.harness import ensure_harness_structure, ensure_harness_structure_synced
from app.services.workspace_instruction_files import (
    AGENTS_INSTRUCTIONS_NAME,
    HARO_INSTRUCTIONS_NAME,
    agents_template,
    haro_template,
    load_user_instruction_context,
)
from app.services.workspace_file_db import list_workspace_directory_page
from app.services.tool_registry import build_tool_descriptions


def test_harness_creates_user_instruction_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    ensure_harness_structure(str(workspace), "u1", initialize_git=False)

    user_root = workspace / "playground" / "users" / "u1"
    assert (user_root / HARO_INSTRUCTIONS_NAME).read_text(encoding="utf-8") == haro_template("u1")
    assert (user_root / AGENTS_INSTRUCTIONS_NAME).read_text(encoding="utf-8") == agents_template()
    assert "내 폴더/결과/{적절한 폴더 이름}/{적절한 파일 이름}" in (user_root / HARO_INSTRUCTIONS_NAME).read_text(encoding="utf-8")


def test_instruction_files_are_visible_in_developer_listing_after_sync(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    ensure_harness_structure_synced(str(workspace), "u1", initialize_git=False)

    developer_page = list_workspace_directory_page(
        str(workspace),
        "/playground/users/u1",
        include_hidden=True,
        user_id="u1",
    )
    user_page = list_workspace_directory_page(
        str(workspace),
        "/playground/users/u1",
        include_hidden=False,
        user_id="u1",
    )

    assert {item["name"] for item in developer_page["items"]} >= {HARO_INSTRUCTIONS_NAME, AGENTS_INSTRUCTIONS_NAME}
    assert HARO_INSTRUCTIONS_NAME not in {item["name"] for item in user_page["items"]}
    assert AGENTS_INSTRUCTIONS_NAME in {item["name"] for item in user_page["items"]}


def test_haro_is_system_template_and_agents_is_user_preserved(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    user_root = workspace / "playground" / "users" / "u1"
    user_root.mkdir(parents=True)
    (user_root / HARO_INSTRUCTIONS_NAME).write_text("user edit", encoding="utf-8")
    (user_root / AGENTS_INSTRUCTIONS_NAME).write_text("custom preference", encoding="utf-8")

    ensure_harness_structure(str(workspace), "u1", initialize_git=False)

    assert (user_root / HARO_INSTRUCTIONS_NAME).read_text(encoding="utf-8") == haro_template("u1")
    assert (user_root / AGENTS_INSTRUCTIONS_NAME).read_text(encoding="utf-8") == "custom preference"


def test_instruction_context_loads_haro_before_agents(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    ensure_harness_structure(str(workspace), "u1", initialize_git=False)
    user_root = workspace / "playground" / "users" / "u1"
    (user_root / AGENTS_INSTRUCTIONS_NAME).write_text("사용자 선호", encoding="utf-8")

    context = load_user_instruction_context(str(workspace), "u1")

    assert context.index(HARO_INSTRUCTIONS_NAME) < context.index(AGENTS_INSTRUCTIONS_NAME)
    assert "사용자 선호" in context


def test_build_context_includes_user_instruction_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    ensure_harness_structure(str(workspace), "u1", initialize_git=False)
    project = Project(id="p1", user_id="u1", title="Project", workspace_path=str(workspace))
    chat = ChatSession(id="c1", project_id="p1", title="Chat", folder_path="/playground/users/u1/50_chats/chat")

    parts = asyncio.run(build_context(None, project, chat))  # type: ignore[arg-type]
    joined = "\n".join(parts)

    assert f"[사용자별 시스템 지침: {HARO_INSTRUCTIONS_NAME}]" in joined
    assert f"[사용자 커스텀 지침: {AGENTS_INSTRUCTIONS_NAME}]" in joined
    assert joined.index(f"[사용자별 시스템 지침: {HARO_INSTRUCTIONS_NAME}]") < joined.index("[현재 하네스 브리핑]")
    assert "내 폴더/결과/{적절한 폴더 이름}/{적절한 파일 이름}" in joined
    assert "명시적인 파일 저장 요청의 기본 위치" not in joined
    assert "/30_outputs/2026-" not in joined
    assert "chat id를 사용자 결과 폴더명으로 사용하지 마세요" in joined


def test_tool_descriptions_require_clear_user_result_paths() -> None:
    text = build_tool_descriptions(["file_create"])

    assert "내 폴더/결과/{적절한 폴더}/{적절한 파일명}" in text
    assert "먼저 질문" in text
    assert "채팅별 폴더" not in text
    assert "현재 채팅 작업공간의 `outputs`, `working`은 임시/중간 산출물에만 사용" in text
