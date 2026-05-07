from __future__ import annotations

import os
from datetime import datetime, timezone


def validate_workspace_path(workspace: str, requested: str) -> str:
    """Validate that requested path stays within workspace. Raises PermissionError on escape."""
    workspace_real = os.path.realpath(workspace)
    full = os.path.realpath(os.path.join(workspace_real, requested.lstrip("/")))
    try:
        inside_workspace = os.path.commonpath([workspace_real, full]) == workspace_real
    except ValueError:
        inside_workspace = False
    if not inside_workspace:
        raise PermissionError("Path traversal denied: outside workspace")
    return full


def build_command(filename: str) -> list[str]:
    if filename.endswith(".ts") or filename.endswith(".js"):
        return ["deno", "run", "--allow-all", f"/workspace/{filename}"]
    if filename.endswith(".py"):
        return ["python3", f"/workspace/{filename}"]
    return ["cat", f"/workspace/{filename}"]


def docker_status_to_project_status(actual_status: str) -> str:
    if actual_status == "running":
        return "running"
    if actual_status in ("exited", "dead"):
        return "stopped"
    return actual_status


def decode_exec_output(output: tuple[bytes | None, bytes | None]) -> tuple[str, str]:
    stdout_bytes = output[0] if output[0] else b""
    stderr_bytes = output[1] if output[1] else b""
    return (
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
    )


def is_project_idle(last_activity_at: str, idle_minutes: int, now: datetime | None = None) -> bool:
    current_time = now or datetime.now(timezone.utc)
    last_activity = datetime.fromisoformat(last_activity_at)
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    elapsed = (current_time - last_activity).total_seconds() / 60
    return elapsed >= idle_minutes
