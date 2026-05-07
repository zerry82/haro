from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.container_manager import ContainerManager, validate_workspace_path
from app.services.container_runtime import (
    build_command,
    decode_exec_output,
    docker_status_to_project_status,
    is_project_idle,
)


def test_build_command_selects_runtime_by_extension() -> None:
    assert build_command("main.ts") == ["deno", "run", "--allow-all", "/workspace/main.ts"]
    assert build_command("main.js") == ["deno", "run", "--allow-all", "/workspace/main.js"]
    assert build_command("script.py") == ["python3", "/workspace/script.py"]
    assert build_command("README.md") == ["cat", "/workspace/README.md"]
    assert ContainerManager.build_command("script.py") == ["python3", "/workspace/script.py"]


def test_validate_workspace_path_rejects_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(PermissionError):
        validate_workspace_path(str(workspace), "../outside.py")

    inside = workspace / "src" / "main.py"
    assert validate_workspace_path(str(workspace), "src/main.py") == str(inside.resolve())


def test_decode_exec_output_handles_missing_streams() -> None:
    assert decode_exec_output((b"hello", None)) == ("hello", "")
    assert decode_exec_output((None, "에러".encode("utf-8"))) == ("", "에러")


def test_docker_status_and_idle_helpers() -> None:
    assert docker_status_to_project_status("running") == "running"
    assert docker_status_to_project_status("exited") == "stopped"
    assert docker_status_to_project_status("paused") == "paused"

    now = datetime(2026, 5, 7, 1, 0, tzinfo=timezone.utc)
    assert is_project_idle("2026-05-07T00:54:00+00:00", 5, now) is True
    assert is_project_idle("2026-05-07T00:56:00+00:00", 5, now) is False
