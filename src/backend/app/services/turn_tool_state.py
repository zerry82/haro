from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


SEARCH_STATEFUL_TOOLS = {"file_search", "dir_list", "file_search_content"}
VERIFY_FILE_TOOLS = {"file_read", "file_stats", "file_search_content", "file_read_range"}
VERIFY_DIR_TOOLS = {"dir_list"}
WRITE_GUARDED_TOOLS = {
    "file_write",
    "file_edit",
    "file_append",
    "file_replace_range",
    "file_delete",
    "file_move",
    "dir_delete",
}


@dataclass
class ToolStateGuardResult:
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnToolState:
    search_signatures: set[str] = field(default_factory=set)
    verified_file_paths: set[str] = field(default_factory=set)
    verified_dir_paths: set[str] = field(default_factory=set)
    blocked_writes: list[dict[str, Any]] = field(default_factory=list)

    def before_tool(self, tool_name: str, tool_args: object) -> ToolStateGuardResult | None:
        duplicate = self._duplicate_search_result(tool_name, tool_args)
        if duplicate:
            return ToolStateGuardResult(duplicate, {"kind": "duplicate_search"})

        missing = self._missing_verified_paths(tool_name, tool_args)
        if missing:
            result = (
                f"도구 상태 가드: `{tool_name}` 실행 전에 대상 경로를 먼저 확인해야 합니다. "
                f"확인되지 않은 경로: {', '.join(missing)}. "
                "`file_read`, `file_stats`, `file_search_content`, `file_read_range`, `dir_list` 중 "
                "적절한 도구로 대상 구조와 최신 상태를 확인한 뒤 다시 호출하세요."
            )
            payload = {"kind": "write_before_read", "missing_paths": missing}
            self.blocked_writes.append({"tool": tool_name, **payload})
            return ToolStateGuardResult(result, payload)
        return None

    def after_tool(self, tool_name: str, tool_args: object, result: str) -> None:
        if result.startswith(("도구 사용 차단:", "도구 상태 가드:", "중복 탐색 생략:")):
            return
        if tool_name in VERIFY_FILE_TOOLS:
            path = _primary_path(tool_args)
            if path:
                self.verified_file_paths.add(path)
        if tool_name in VERIFY_DIR_TOOLS:
            path = _primary_path(tool_args)
            if path:
                self.verified_dir_paths.add(path)

    def _duplicate_search_result(self, tool_name: str, tool_args: object) -> str | None:
        if tool_name not in SEARCH_STATEFUL_TOOLS:
            return None
        signature = tool_call_signature(tool_name, tool_args)
        if signature in self.search_signatures:
            return (
                f"중복 탐색 생략: `{tool_name}`에 동일한 인자를 이미 사용했습니다. "
                "직전 도구 결과와 현재 작업 맥락의 File Discovery 후보를 바탕으로 다음 단계를 판단하세요. "
                "새 위치나 새 검색어가 없다면 사용자에게 파일 경로 또는 재업로드를 요청하세요."
            )
        self.search_signatures.add(signature)
        return None

    def _missing_verified_paths(self, tool_name: str, tool_args: object) -> list[str]:
        if tool_name not in WRITE_GUARDED_TOOLS:
            return []
        paths = _guarded_paths(tool_name, tool_args)
        missing: list[str] = []
        for path in paths:
            if tool_name == "dir_delete":
                if path not in self.verified_dir_paths:
                    missing.append(path)
            elif path not in self.verified_file_paths and path not in self.verified_dir_paths:
                missing.append(path)
        return missing


def tool_call_signature(tool_name: str, tool_args: object) -> str:
    normalized_args = normalize_tool_args(tool_args)
    return json.dumps({"tool": tool_name, "args": normalized_args}, ensure_ascii=False, sort_keys=True)


def normalize_tool_args(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): normalize_tool_args(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [normalize_tool_args(item) for item in value]
    if isinstance(value, str):
        return _normalize_path_or_text(value)
    return value


def _guarded_paths(tool_name: str, tool_args: object) -> list[str]:
    if not isinstance(tool_args, dict):
        return []
    if tool_name == "file_move":
        source = _normalize_path_or_text(str(tool_args.get("source_path") or ""))
        return [source] if source else []
    path = _primary_path(tool_args)
    return [path] if path else []


def _primary_path(tool_args: object) -> str | None:
    if not isinstance(tool_args, dict):
        return None
    path = tool_args.get("path")
    if path is None:
        return None
    normalized = _normalize_path_or_text(str(path))
    return normalized or None


def _normalize_path_or_text(value: str) -> str:
    return " ".join((value or "").replace("\\", "/").split())
