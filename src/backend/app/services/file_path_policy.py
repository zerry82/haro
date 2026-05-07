from __future__ import annotations

import os

from fastapi import HTTPException

from app.services.harness import is_clean_room_path, is_haro_internal_path


def assert_read_allowed(requested: str) -> None:
    if is_haro_internal_path(requested):
        raise HTTPException(status_code=403, detail="Haro internal metadata is not accessible")


def assert_write_allowed(requested: str) -> None:
    assert_read_allowed(requested)
    if is_clean_room_path(requested):
        raise HTTPException(status_code=403, detail="Clean Room is read-only")


def validate_workspace_path(workspace: str, requested: str) -> str:
    workspace_real = os.path.realpath(workspace)
    full = os.path.realpath(os.path.join(workspace_real, requested.lstrip("/")))
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
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail=f"Invalid file name: {name}")
