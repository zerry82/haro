from __future__ import annotations

import json
from pathlib import Path

from app.models.chat_session import ChatSession
from app.services.chat_workspace_lifecycle import ensure_chat_workspace
from app.services.chat_workspace_references import (
    export_chat_file,
    get_latest_chat_output_reference,
    get_latest_chat_preview_reference,
    record_file_reference,
    record_preview_reference,
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


def test_record_file_reference_updates_linked_files_and_latest_output(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    chat = _chat()
    ensure_chat_workspace(str(workspace), "u", chat)

    output = workspace / "playground" / "users" / "u" / "50_chats" / "chat" / "outputs" / "report.md"
    output.write_text("# Report\n", encoding="utf-8")
    record_file_reference(str(workspace), chat, "outputs", "/playground/users/u/50_chats/chat/outputs/report.md", action="created")

    linked = json.loads((workspace / "playground" / "users" / "u" / "50_chats" / "chat" / "linked-files.json").read_text())
    assert linked["outputs"] == [
        {"path": "/playground/users/u/50_chats/chat/outputs/report.md", "action": "created"}
    ]
    assert get_latest_chat_output_reference(str(workspace), chat) == {
        "kind": "outputs",
        "path": "/playground/users/u/50_chats/chat/outputs/report.md",
        "action": "created",
    }


def test_preview_reference_and_export_tracking(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    chat = _chat()
    ensure_chat_workspace(str(workspace), "u", chat)

    source = workspace / "playground" / "users" / "u" / "50_chats" / "chat" / "outputs" / "page.html"
    source.write_text("<h1>Hello</h1>", encoding="utf-8")
    target = "/playground/users/u/30_outputs/page.html"

    exported = export_chat_file(
        str(workspace),
        chat,
        "/playground/users/u/50_chats/chat/outputs/page.html",
        target,
    )
    record_preview_reference(str(workspace), chat, "http://localhost:8080", ip="127.0.0.1")

    assert exported == target
    assert (workspace / "playground" / "users" / "u" / "30_outputs" / "page.html").is_file()
    assert get_latest_chat_preview_reference(str(workspace), chat) == {
        "kind": "preview",
        "url": "http://localhost:8080",
        "ip": "127.0.0.1",
        "action": "preview_ready",
    }
