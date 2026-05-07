from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone

from app.models.chat_session import ChatSession
from app.services.chat_workspace_files import load_json_file, write_json_file
from app.services.chat_workspace_paths import full_path
from app.services.harness import normalize_workspace_path
from app.services.workspace_file_db import record_workspace_relation, sync_workspace_subtree

LINKED_FILES_FALLBACK = {
    "inputs": [],
    "derived": [],
    "outputs": [],
    "exports": [],
}


def record_file_reference(
    workspace: str,
    chat: ChatSession,
    kind: str,
    path: str,
    *,
    action: str | None = None,
    target_path: str | None = None,
) -> None:
    if not chat.folder_path:
        return
    linked = load_json_file(workspace, chat.folder_path, "linked-files.json", LINKED_FILES_FALLBACK)
    for key in ("inputs", "derived", "outputs", "exports"):
        linked.setdefault(key, [])
    normalized = normalize_workspace_path(path)

    if kind == "exports":
        entry = {
            "source_path": normalized,
            "target_path": normalize_workspace_path(target_path),
            "action": action or "exported",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        if entry not in linked["exports"]:
            linked["exports"].append(entry)
        record_workspace_relation(
            workspace,
            "exported_to",
            from_path=normalized,
            to_path=entry["target_path"],
            chat_id=chat.id,
        )
    else:
        entry = {"path": normalized, "action": action or kind}
        if entry not in linked[kind]:
            linked[kind].append(entry)
        relation_type = "chat_input" if kind == "inputs" else "chat_output" if kind == "outputs" else "derived_from"
        if relation_type == "chat_input":
            record_workspace_relation(workspace, relation_type, from_path=normalized, to_path=chat.folder_path, chat_id=chat.id)
        else:
            record_workspace_relation(workspace, relation_type, from_path=chat.folder_path, to_path=normalized, chat_id=chat.id)

    write_json_file(workspace, chat.folder_path, "linked-files.json", linked)


def record_preview_reference(
    workspace: str,
    chat: ChatSession,
    url: str,
    *,
    ip: str | None = None,
    action: str | None = None,
) -> None:
    if not chat.folder_path:
        return
    linked = load_json_file(workspace, chat.folder_path, "linked-files.json", {
        **LINKED_FILES_FALLBACK,
        "previews": [],
    })
    for key in ("inputs", "derived", "outputs", "exports", "previews"):
        linked.setdefault(key, [])

    entry = {
        "url": url,
        "ip": ip,
        "action": action or "preview_ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    linked["previews"].append(entry)
    write_json_file(workspace, chat.folder_path, "linked-files.json", linked)


def get_latest_chat_output_reference(workspace: str, chat: ChatSession | None) -> dict | None:
    if not chat or not chat.folder_path:
        return None
    linked = load_json_file(workspace, chat.folder_path, "linked-files.json", LINKED_FILES_FALLBACK)
    outputs = linked.get("outputs") or []
    if outputs:
        latest = outputs[-1]
        path = latest.get("path")
        if path:
            return {
                "kind": "outputs",
                "path": normalize_workspace_path(path),
                "action": latest.get("action"),
            }
    exports = linked.get("exports") or []
    if exports:
        latest = exports[-1]
        path = latest.get("target_path") or latest.get("source_path")
        if path:
            return {
                "kind": "exports",
                "path": normalize_workspace_path(path),
                "action": latest.get("action"),
            }
    return None


def get_latest_chat_preview_reference(workspace: str, chat: ChatSession | None) -> dict | None:
    if not chat or not chat.folder_path:
        return None
    linked = load_json_file(workspace, chat.folder_path, "linked-files.json", {
        **LINKED_FILES_FALLBACK,
        "previews": [],
    })
    previews = linked.get("previews") or []
    if not previews:
        return None
    latest = previews[-1]
    url = latest.get("url")
    if not url:
        return None
    return {
        "kind": "preview",
        "url": str(url),
        "ip": latest.get("ip"),
        "action": latest.get("action"),
    }


def export_chat_file(workspace: str, chat: ChatSession, source_path: str, target_path: str) -> str:
    source = normalize_workspace_path(source_path)
    target = normalize_workspace_path(target_path)
    source_full = full_path(workspace, source)
    target_full = full_path(workspace, target)
    if not os.path.isfile(source_full):
        raise FileNotFoundError(f"Source file not found: {source}")
    os.makedirs(os.path.dirname(target_full), exist_ok=True)
    shutil.copy2(source_full, target_full)
    record_file_reference(workspace, chat, "exports", source, target_path=target)
    sync_workspace_subtree(workspace, target, source_kind="chat", chat_id=chat.id)
    return target
