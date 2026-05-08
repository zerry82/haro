from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from app.services.harness import normalize_workspace_path


TEAM_FOLDER = "팀 폴더"
MY_FOLDER = "내 폴더"
TEAM_FOLDER_COMPACT = "팀폴더"
MY_FOLDER_COMPACT = "내폴더"
RESULT_FOLDER = "결과폴더"


@dataclass(frozen=True)
class WorkspacePathAlias:
    alias_prefix: str
    canonical_prefix: str


def workspace_aliases(user_id: str) -> tuple[WorkspacePathAlias, ...]:
    user_root = f"/playground/users/{user_id}"
    return (
        WorkspacePathAlias(f"{TEAM_FOLDER}/데이터", "/clean-room/data"),
        WorkspacePathAlias(f"{TEAM_FOLDER}/규칙/스킬", "/clean-room/meta"),
        WorkspacePathAlias(f"{TEAM_FOLDER}/공유 결과", "/clean-room/data/30_outputs"),
        WorkspacePathAlias(f"{MY_FOLDER}/받은 파일", f"{user_root}/00_inbox"),
        WorkspacePathAlias(f"{MY_FOLDER}/작업 중", f"{user_root}/20_working"),
        WorkspacePathAlias(f"{MY_FOLDER}/결과", f"{user_root}/30_outputs"),
        WorkspacePathAlias(f"{MY_FOLDER}/AGENTS.md", f"{user_root}/AGENTS.md"),
        WorkspacePathAlias(TEAM_FOLDER, "/clean-room"),
        WorkspacePathAlias(MY_FOLDER, user_root),
    )


def user_visible_canonical_prefixes(user_id: str) -> tuple[str, ...]:
    return (
        "/clean-room/data",
        "/clean-room/meta",
        f"/playground/users/{user_id}/00_inbox",
        f"/playground/users/{user_id}/20_working",
        f"/playground/users/{user_id}/30_outputs",
        f"/playground/users/{user_id}/AGENTS.md",
    )


def resolve_workspace_alias_path(path: str | None, user_id: str) -> str:
    if not path:
        return "/"
    alias_path = path.replace("\\", "/").strip().strip("/")
    if not alias_path:
        return "/"
    alias_path = _normalize_alias_synonyms(alias_path)

    aliases = sorted(workspace_aliases(user_id), key=lambda item: len(item.alias_prefix), reverse=True)
    for alias in aliases:
        if alias_path == alias.alias_prefix:
            return normalize_workspace_path(alias.canonical_prefix)
        if alias.alias_prefix in {TEAM_FOLDER, MY_FOLDER}:
            continue
        if alias_path.startswith(f"{alias.alias_prefix}/"):
            rest = alias_path[len(alias.alias_prefix):].lstrip("/")
            canonical = f"{alias.canonical_prefix.rstrip('/')}/{rest}"
            return normalize_workspace_path(canonical)

    first_segment = alias_path.split("/", 1)[0]
    if first_segment in {TEAM_FOLDER, MY_FOLDER}:
        raise HTTPException(status_code=400, detail=f"Unknown workspace alias path: {path}")

    return normalize_workspace_path(path)


def alias_path_for_canonical_path(path: str | None, user_id: str) -> str:
    canonical = normalize_workspace_path(path)
    aliases = sorted(workspace_aliases(user_id), key=lambda item: len(item.canonical_prefix), reverse=True)
    for alias in aliases:
        prefix = normalize_workspace_path(alias.canonical_prefix)
        if canonical == prefix or canonical.startswith(f"{prefix.rstrip('/')}/"):
            rest = canonical[len(prefix):].lstrip("/")
            return alias.alias_prefix if not rest else f"{alias.alias_prefix}/{rest}"
    return canonical


def _normalize_alias_synonyms(path: str) -> str:
    if path == MY_FOLDER_COMPACT or path.startswith(f"{MY_FOLDER_COMPACT}/"):
        return f"{MY_FOLDER}{path[len(MY_FOLDER_COMPACT):]}"
    if path == TEAM_FOLDER_COMPACT or path.startswith(f"{TEAM_FOLDER_COMPACT}/"):
        return f"{TEAM_FOLDER}{path[len(TEAM_FOLDER_COMPACT):]}"
    if path == RESULT_FOLDER:
        return f"{MY_FOLDER}/결과"
    if path.startswith(f"{RESULT_FOLDER}/"):
        return f"{MY_FOLDER}/결과/{path[len(RESULT_FOLDER):].lstrip('/')}"
    return path
