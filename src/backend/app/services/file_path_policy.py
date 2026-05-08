from __future__ import annotations

import os
import re

from fastapi import HTTPException

from app.services.harness import is_clean_room_path, is_haro_internal_path, normalize_workspace_path
from app.services.workspace_visibility_policy import assert_user_mutation_path_allowed
from app.services.workspace_instruction_files import is_user_haro_path


WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def assert_read_allowed(requested: str, user_id: str | None = None) -> None:
    if is_haro_internal_path(requested):
        raise HTTPException(status_code=403, detail="Haro internal metadata is not accessible")
    normalized = normalize_workspace_path(requested)
    if normalized.endswith("/.HARO.md") or is_user_haro_path(requested, user_id):
        raise HTTPException(status_code=403, detail=".HARO.md is system-managed")


def assert_write_allowed(requested: str, user_id: str | None = None) -> None:
    assert_read_allowed(requested, user_id)
    if is_clean_room_path(requested):
        raise HTTPException(status_code=403, detail="Clean Room is read-only")
    assert_user_mutation_path_allowed(requested)


def validate_workspace_path(workspace: str, requested: str) -> str:
    _assert_workspace_path_input_allowed(requested)
    normalized = normalize_workspace_path(requested)
    workspace_real = os.path.realpath(workspace)
    full = os.path.realpath(os.path.join(workspace_real, normalized.lstrip("/")))
    try:
        inside_workspace = os.path.commonpath([workspace_real, full]) == workspace_real
    except ValueError:
        inside_workspace = False
    if not inside_workspace:
        raise HTTPException(status_code=403, detail="Path traversal denied")
    return full


def join_workspace_path(base_path: str, name: str) -> str:
    return f"/{name}" if base_path == "/" else f"{base_path.rstrip('/')}/{name}"


def validate_file_name(name: str) -> None:
    if not name or name in {".", ".."} or name.startswith(".") or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail=f"Invalid file name: {name}")


def validate_user_path_for_mutation(path: str, user_id: str | None = None) -> None:
    _assert_workspace_path_input_allowed(path)
    assert_user_mutation_path_allowed(path)


def _assert_workspace_path_input_allowed(requested: str | None) -> None:
    raw = (requested or "").strip()
    normalized_slashes = raw.replace("\\", "/")
    stripped = normalized_slashes.lstrip("/")
    first_segment = stripped.split("/", 1)[0] if stripped else ""

    if normalized_slashes.startswith("//") or raw.startswith("\\\\"):
        raise HTTPException(status_code=403, detail="Path traversal denied")
    if WINDOWS_DRIVE_RE.match(first_segment):
        raise HTTPException(status_code=403, detail="Path traversal denied")
    if any(part == ".." for part in normalized_slashes.split("/")):
        raise HTTPException(status_code=403, detail="Path traversal denied")
