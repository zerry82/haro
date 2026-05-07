from __future__ import annotations

import os

from app.models.chat_session import ChatSession
from app.services.chat_workspace_files import ensure_json_file, ensure_text_file
from app.services.chat_workspace_paths import default_chat_folder_path, full_path
from app.services.chat_workspace_templates import context_template, readme_template
from app.services.harness import normalize_workspace_path
from app.services.workspace_file_db import sync_workspace_subtree


def ensure_chat_workspace(workspace: str, user_id: str, chat: ChatSession) -> str:
    """Create the on-disk chat workspace and return its workspace-relative path."""
    if not chat.folder_path:
        chat.folder_path = default_chat_folder_path(user_id, chat)

    folder_path = normalize_workspace_path(chat.folder_path)
    chat.folder_path = folder_path

    full_dir = full_path(workspace, folder_path)
    for relative in ("inputs", "working", "outputs", "summaries"):
        os.makedirs(os.path.join(full_dir, relative), exist_ok=True)

    ensure_text_file(workspace, folder_path, "README.md", readme_template(chat))
    ensure_text_file(workspace, folder_path, "conversation.md", "# Conversation\n\n")
    ensure_text_file(workspace, folder_path, "context.md", context_template(chat))
    ensure_text_file(workspace, folder_path, "decisions.md", "# Decisions\n\n")
    ensure_text_file(workspace, folder_path, "rule-candidates.md", "# Rule Candidates\n\n")
    ensure_text_file(workspace, folder_path, "agent-log.md", "# Agent Log\n\n")
    ensure_json_file(workspace, folder_path, "linked-files.json", {
        "inputs": [],
        "derived": [],
        "outputs": [],
        "exports": [],
    })
    ensure_json_file(workspace, folder_path, "artifacts.json", {"artifacts": []})
    ensure_json_file(workspace, f"{folder_path}/summaries", "index.json", {"summaries": []})
    sync_workspace_subtree(workspace, folder_path, source_kind="chat", chat_id=chat.id)
    return folder_path
