from __future__ import annotations

from fastapi import HTTPException

from app.services.harness import normalize_workspace_path
from app.services.workspace_aliases import user_visible_canonical_prefixes


def has_dot_prefixed_segment(path: str | None) -> bool:
    normalized = normalize_workspace_path(path)
    return any(segment.startswith(".") for segment in normalized.strip("/").split("/") if segment)


def is_system_hidden_path(path: str | None) -> bool:
    return has_dot_prefixed_segment(path)


def assert_user_mutation_path_allowed(path: str | None) -> None:
    if has_dot_prefixed_segment(path):
        raise HTTPException(status_code=400, detail="Names starting with '.' are reserved for system files")


def hidden_path_sql_condition(column: str = "path") -> str:
    return f"{column} NOT LIKE '/.%' ESCAPE '\\' AND {column} NOT LIKE '%/.%' ESCAPE '\\'"


def user_visible_sql_condition(
    user_id: str,
    *,
    column: str = "path",
    include_ancestors: bool = False,
) -> tuple[str, list[str]]:
    prefixes = user_visible_canonical_prefixes(user_id)
    clauses: list[str] = []
    params: list[str] = []
    for prefix in prefixes:
        normalized = normalize_workspace_path(prefix)
        like_prefix = f"{_escape_like(normalized.rstrip('/'))}/%"
        if include_ancestors:
            clauses.append(f"({column} = ? OR {column} LIKE ? ESCAPE '\\' OR ? LIKE {column} || '/%')")
            params.extend([normalized, like_prefix, normalized])
        else:
            clauses.append(f"({column} = ? OR {column} LIKE ? ESCAPE '\\')")
            params.extend([normalized, like_prefix])
    return f"({' OR '.join(clauses)})", params


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
