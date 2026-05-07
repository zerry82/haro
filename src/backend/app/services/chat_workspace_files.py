from __future__ import annotations

import json
import os

from app.services.chat_workspace_paths import full_path


def ensure_text_file(workspace: str, folder_path: str, name: str, content: str) -> None:
    full = full_path(workspace, f"{folder_path}/{name}")
    if os.path.exists(full):
        return
    write_text_file(workspace, folder_path, name, content)


def ensure_json_file(workspace: str, folder_path: str, name: str, content: dict) -> None:
    full = full_path(workspace, f"{folder_path}/{name}")
    if os.path.exists(full):
        return
    write_json_file(workspace, folder_path, name, content)


def append_text(workspace: str, folder_path: str, name: str, content: str) -> None:
    full = full_path(workspace, f"{folder_path}/{name}")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "a", encoding="utf-8") as f:
        f.write(content)


def write_text_file(workspace: str, folder_path: str, name: str, content: str) -> None:
    full = full_path(workspace, f"{folder_path}/{name}")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def load_json_file(workspace: str, folder_path: str, name: str, fallback: dict) -> dict:
    full = full_path(workspace, f"{folder_path}/{name}")
    if not os.path.isfile(full):
        return json.loads(json.dumps(fallback))
    try:
        with open(full, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return json.loads(json.dumps(fallback))


def write_json_file(workspace: str, folder_path: str, name: str, content: dict) -> None:
    full = full_path(workspace, f"{folder_path}/{name}")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
        f.write("\n")
