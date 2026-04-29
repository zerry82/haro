from __future__ import annotations

import logging
import os
import posixpath
import shutil
import subprocess
from datetime import datetime, timezone

from app.services.workspace_index import LEGACY_META_DIR, META_DIR

logger = logging.getLogger(__name__)

CLEAN_ROOM_DIR = "clean-room"
PLAYGROUND_DIR = "playground"
ARCHIVE_DIR = "90_archive"

DATA_CLEAN_ROOM_REPO = "data-clean-room.git"
META_CLEAN_ROOM_REPO = "meta-clean-room.git"


def normalize_workspace_path(path: str | None) -> str:
    value = (path or "/").replace("\\", "/").strip()
    normalized = posixpath.normpath("/" + value.lstrip("/"))
    return "/" if normalized == "/." else normalized


def is_haro_internal_path(path: str | None) -> bool:
    normalized = normalize_workspace_path(path)
    return any(
        normalized == f"/{root}" or normalized.startswith(f"/{root}/")
        for root in (META_DIR, LEGACY_META_DIR)
    )


def is_clean_room_path(path: str | None) -> bool:
    normalized = normalize_workspace_path(path)
    return normalized == f"/{CLEAN_ROOM_DIR}" or normalized.startswith(f"/{CLEAN_ROOM_DIR}/")


def get_playground_inbox_path(user_id: str) -> str:
    return f"/{PLAYGROUND_DIR}/users/{user_id}/00_inbox"


def ensure_harness_structure(workspace: str, user_id: str, initialize_git: bool = True) -> None:
    for relative_path in _harness_directories(user_id):
        os.makedirs(os.path.join(workspace, *relative_path.split("/")), exist_ok=True)

    if initialize_git:
        _ensure_clean_room_git(workspace)


def _harness_directories(user_id: str) -> list[str]:
    return [
        "clean-room/data/00_inbox",
        "clean-room/data/10_sources",
        "clean-room/data/30_outputs",
        "clean-room/data/templates",
        "clean-room/meta/40_rules",
        "clean-room/meta/45_skills",
        "clean-room/meta/schemas",
        "clean-room/meta/validators",
        "clean-room/meta/triggers",
        "clean-room/meta/hooks",
        "clean-room/meta/policies",
        "clean-room/meta/50_chats",
        f"playground/users/{user_id}/00_inbox",
        f"playground/users/{user_id}/20_working",
        f"playground/users/{user_id}/30_outputs",
        f"playground/users/{user_id}/40_rules",
        f"playground/users/{user_id}/45_skills",
        f"playground/users/{user_id}/50_chats",
        "90_archive",
        ".haro/git",
        ".haro/file_summaries",
        ".haro/context/self",
        ".haro/context/contacts",
        ".haro/context/source-refs",
    ]


def _ensure_clean_room_git(workspace: str) -> None:
    git = shutil.which("git")
    if not git:
        logger.warning("git executable not found; clean room git repositories were not initialized")
        return

    git_root = os.path.join(workspace, META_DIR, "git")
    os.makedirs(git_root, exist_ok=True)

    for repo_name in (DATA_CLEAN_ROOM_REPO, META_CLEAN_ROOM_REPO):
        repo_path = os.path.join(git_root, repo_name)
        try:
            if not os.path.isdir(repo_path):
                _run_git(git, ["init", "--bare", repo_path])
            _ensure_initial_commit(git, repo_path)
        except Exception as exc:
            logger.warning("Failed to initialize %s: %s", repo_name, exc)


def _ensure_initial_commit(git: str, repo_path: str) -> None:
    if _git_ref_exists(git, repo_path, "refs/heads/main"):
        return

    tree_sha = _run_git(git, ["--git-dir", repo_path, "mktree"], input_text="").stdout.strip()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "haro",
        "GIT_AUTHOR_EMAIL": "haro@example.local",
        "GIT_COMMITTER_NAME": "haro",
        "GIT_COMMITTER_EMAIL": "haro@example.local",
        "GIT_AUTHOR_DATE": datetime.now(timezone.utc).isoformat(),
        "GIT_COMMITTER_DATE": datetime.now(timezone.utc).isoformat(),
    }
    commit_sha = _run_git(
        git,
        ["--git-dir", repo_path, "commit-tree", tree_sha, "-m", "Initial clean room checkpoint"],
        env=env,
    ).stdout.strip()
    _run_git(git, ["--git-dir", repo_path, "update-ref", "refs/heads/main", commit_sha])
    _run_git(git, ["--git-dir", repo_path, "symbolic-ref", "HEAD", "refs/heads/main"])


def _git_ref_exists(git: str, repo_path: str, ref: str) -> bool:
    result = subprocess.run(
        [git, "--git-dir", repo_path, "rev-parse", "--verify", ref],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _run_git(
    git: str,
    args: list[str],
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [git, *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
