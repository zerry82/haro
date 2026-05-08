from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import PROJECT_ROOT, Settings
from app.services.file_path_policy import (
    assert_read_allowed,
    assert_write_allowed,
    join_workspace_path,
    validate_file_name,
    validate_user_path_for_mutation,
    validate_workspace_path,
)
from app.services.workspace_aliases import (
    alias_path_for_canonical_path,
    resolve_workspace_alias_path,
)


def test_validate_workspace_path_denies_traversal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(HTTPException) as exc:
        validate_workspace_path(str(workspace), "../outside.txt")

    assert exc.value.status_code == 403


def test_validate_workspace_path_denies_absolute_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(HTTPException):
        validate_workspace_path(str(workspace), "C:/Windows/system32")

    with pytest.raises(HTTPException):
        validate_workspace_path(str(workspace), "//server/share/file.txt")


def test_validate_workspace_path_denies_symlink_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    link = workspace / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not available in this environment")

    with pytest.raises(HTTPException) as exc:
        validate_workspace_path(str(workspace), "/linked/secret.txt")

    assert exc.value.status_code == 403


def test_validate_workspace_path_allows_paths_inside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    docs = workspace / "docs"
    docs.mkdir(parents=True)

    assert validate_workspace_path(str(workspace), "/docs") == str(docs.resolve())


def test_read_and_write_policies_reject_protected_paths() -> None:
    with pytest.raises(HTTPException) as read_exc:
        assert_read_allowed("/.haro/db/workspace.db", "u1")
    assert read_exc.value.status_code == 403

    with pytest.raises(HTTPException) as write_exc:
        assert_write_allowed("/clean-room/data/source.csv", "u1")
    assert write_exc.value.status_code == 403

    with pytest.raises(HTTPException):
        assert_read_allowed("/playground/users/u1/.HARO.md", "u1")

    with pytest.raises(HTTPException):
        assert_write_allowed("/playground/users/u1/.HARO.md", "u1")

    assert_read_allowed("/playground/users/u1/AGENTS.md", "u1")
    assert_write_allowed("/playground/users/u1/AGENTS.md", "u1")


def test_workspace_path_join_and_name_validation() -> None:
    assert join_workspace_path("/", "a.txt") == "/a.txt"
    assert join_workspace_path("/docs", "a.txt") == "/docs/a.txt"
    validate_file_name("a.txt")
    validate_file_name("data.v1.csv")

    with pytest.raises(HTTPException):
        validate_file_name("../a.txt")

    with pytest.raises(HTTPException):
        validate_file_name(".secret")

    with pytest.raises(HTTPException):
        validate_user_path_for_mutation("/docs/.cache/file.txt")

    validate_user_path_for_mutation("/playground/users/u1/AGENTS.md", "u1")


def test_workspace_alias_paths_resolve_to_canonical_paths() -> None:
    assert resolve_workspace_alias_path("내 폴더/작업 중/report.md", "u1") == "/playground/users/u1/20_working/report.md"
    assert resolve_workspace_alias_path("내 폴더/결과/report.md", "u1") == "/playground/users/u1/30_outputs/report.md"
    assert resolve_workspace_alias_path("내 폴더/AGENTS.md", "u1") == "/playground/users/u1/AGENTS.md"
    assert resolve_workspace_alias_path("내폴더/결과/report.md", "u1") == "/playground/users/u1/30_outputs/report.md"
    assert resolve_workspace_alias_path("결과폴더/report.md", "u1") == "/playground/users/u1/30_outputs/report.md"
    assert resolve_workspace_alias_path("팀 폴더/데이터/source.csv", "u1") == "/clean-room/data/source.csv"
    assert resolve_workspace_alias_path("/clean-room/data/source.csv", "u1") == "/clean-room/data/source.csv"

    with pytest.raises(HTTPException):
        resolve_workspace_alias_path("내 폴더/없는 위치/a.md", "u1")


def test_canonical_paths_convert_to_alias_paths() -> None:
    assert alias_path_for_canonical_path("/playground/users/u1/20_working/report.md", "u1") == "내 폴더/작업 중/report.md"
    assert alias_path_for_canonical_path("/playground/users/u1/AGENTS.md", "u1") == "내 폴더/AGENTS.md"
    assert alias_path_for_canonical_path("/clean-room/data/source.csv", "u1") == "팀 폴더/데이터/source.csv"
    assert alias_path_for_canonical_path("/docs/guide.md", "u1") == "/docs/guide.md"


def test_workspace_root_default_resolves_to_project_runtime() -> None:
    settings = Settings(workspace_root="runtime/workspaces")

    assert settings.workspace_root == str((PROJECT_ROOT / "runtime" / "workspaces").resolve())
