from __future__ import annotations

import os

from app.services.harness import normalize_workspace_path
from app.services.workspace_index import LEGACY_META_DIR, META_DIR


def make_snippet(summary: str, query: str) -> str:
    text = " ".join(summary.split())
    if not text:
        return ""
    lowered = text.lower()
    index = lowered.find(query.lower())
    if index < 0:
        return text[:160]
    start = max(0, index - 50)
    end = min(len(text), index + len(query) + 80)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def classify_path(path: str) -> tuple[str, str, str | None]:
    parts = [part for part in path.strip("/").split("/") if part]
    if not parts:
        return "root", "writable", None
    if parts[0] == "clean-room":
        if len(parts) > 1 and parts[1] == "data":
            return "clean_room_data", "read_only", None
        return "clean_room_meta", "read_only", None
    if parts[0] == "playground":
        owner_user_id = parts[2] if len(parts) >= 3 and parts[1] == "users" else None
        return "playground", "writable", owner_user_id
    if parts[0] == "90_archive":
        return "archive", "read_only", None
    return "root", "writable", None


def language_for_extension(extension: str) -> str | None:
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".csv": "csv",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".txt": "plaintext",
        ".svg": "xml",
    }.get(extension)


def fts_phrase(query: str) -> str:
    return f'"{query.replace(chr(34), chr(34) + chr(34))}"'


def escape_like(query: str) -> str:
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def parent_path(path: str) -> str:
    parent = normalize_workspace_path(os.path.dirname(path.rstrip("/")))
    return parent if parent != "/." else "/"


def workspace_path_from_full(workspace: str, full_path: str) -> str:
    rel = os.path.relpath(full_path, workspace).replace("\\", "/")
    if rel == ".":
        return "/"
    return normalize_workspace_path(rel)


def full_path(workspace: str, requested: str) -> str:
    normalized = normalize_workspace_path(requested)
    workspace_real = os.path.realpath(workspace)
    full = os.path.realpath(os.path.join(workspace_real, normalized.lstrip("/")))
    if os.path.commonpath([workspace_real, full]) != workspace_real:
        raise PermissionError("워크스페이스 외부 접근 불가")
    return full


def db_path(workspace: str) -> str:
    return os.path.join(workspace, META_DIR, "db", "workspace.db")


def is_meta_path(path: str) -> bool:
    normalized = normalize_workspace_path(path)
    return any(normalized == f"/{name}" or normalized.startswith(f"/{name}/") for name in (META_DIR, LEGACY_META_DIR))
