from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.file_path_policy import (
    assert_read_allowed,
    assert_write_allowed,
    join_workspace_path,
    validate_file_name,
    validate_workspace_path,
)


def test_validate_workspace_path_denies_traversal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(HTTPException) as exc:
        validate_workspace_path(str(workspace), "../outside.txt")

    assert exc.value.status_code == 403


def test_validate_workspace_path_allows_paths_inside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    docs = workspace / "docs"
    docs.mkdir(parents=True)

    assert validate_workspace_path(str(workspace), "/docs") == str(docs.resolve())


def test_read_and_write_policies_reject_protected_paths() -> None:
    with pytest.raises(HTTPException) as read_exc:
        assert_read_allowed("/.haro/db/workspace.db")
    assert read_exc.value.status_code == 403

    with pytest.raises(HTTPException) as write_exc:
        assert_write_allowed("/clean-room/data/source.csv")
    assert write_exc.value.status_code == 403


def test_workspace_path_join_and_name_validation() -> None:
    assert join_workspace_path("/", "a.txt") == "/a.txt"
    assert join_workspace_path("/docs", "a.txt") == "/docs/a.txt"
    validate_file_name("a.txt")

    with pytest.raises(HTTPException):
        validate_file_name("../a.txt")
