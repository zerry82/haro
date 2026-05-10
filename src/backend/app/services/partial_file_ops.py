from __future__ import annotations

"""Pure helpers for partial text-file operations."""

import difflib
import fnmatch
import hashlib
import math
import os
import re
from dataclasses import dataclass
from typing import Any


MAX_RANGE_LINES = 500
MAX_SEARCH_RESULTS = 200
MAX_DIFF_CHARS = 8000
SKIPPED_DIRS = {".git", ".haro", "__pycache__", "node_modules"}
SKIPPED_FILE_NAMES = {".HARO.md"}


class PartialFileOperationError(ValueError):
    """Raised when a partial file operation cannot be applied safely."""


class ChecksumMismatchError(PartialFileOperationError):
    """Raised when expected_sha256 does not match the current file."""


@dataclass(frozen=True)
class TextSnapshot:
    path: str
    text: str
    raw: bytes
    sha256: str
    stats: dict[str, Any]


def read_text_snapshot(path: str) -> TextSnapshot:
    if not os.path.isfile(path):
        raise PartialFileOperationError("파일이 없거나 일반 파일이 아닙니다.")
    with open(path, "rb") as file:
        raw = file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PartialFileOperationError("UTF-8 텍스트 파일만 부분 작업할 수 있습니다.") from exc
    if "\x00" in text:
        raise PartialFileOperationError("바이너리로 보이는 파일은 부분 작업할 수 없습니다.")
    sha = hashlib.sha256(raw).hexdigest()
    return TextSnapshot(path=path, text=text, raw=raw, sha256=sha, stats=_stats_for_text(raw, text, sha))


def file_stats(path: str) -> dict[str, Any]:
    return read_text_snapshot(path).stats


def read_range(path: str, *, start_line: int, line_count: int, max_lines: int = MAX_RANGE_LINES) -> dict[str, Any]:
    snapshot = read_text_snapshot(path)
    if start_line < 1:
        raise PartialFileOperationError("start_line은 1 이상이어야 합니다.")
    if line_count < 1:
        raise PartialFileOperationError("line_count는 1 이상이어야 합니다.")
    warnings: list[str] = []
    requested_count = line_count
    if line_count > max_lines:
        line_count = max_lines
        warnings.append(f"line_count가 최대 {max_lines}줄로 제한되었습니다.")

    lines = snapshot.text.splitlines(keepends=True)
    total_lines = len(snapshot.text.splitlines()) if snapshot.text else 0
    if total_lines == 0:
        return {
            "start_line": start_line,
            "end_line": 0,
            "total_lines": 0,
            "requested_line_count": requested_count,
            "content": "",
            "sha256": snapshot.sha256,
            "warnings": warnings,
        }
    if start_line > total_lines:
        warnings.append("start_line이 파일 끝을 넘어가 내용이 비어 있습니다.")
        return {
            "start_line": start_line,
            "end_line": total_lines,
            "total_lines": total_lines,
            "requested_line_count": requested_count,
            "content": "",
            "sha256": snapshot.sha256,
            "warnings": warnings,
        }

    start_index = start_line - 1
    end_index = min(total_lines, start_index + line_count)
    if end_index < start_index + line_count:
        warnings.append("파일 끝까지만 반환했습니다.")
    selected = lines[start_index:end_index]
    return {
        "start_line": start_line,
        "end_line": start_line + len(selected) - 1,
        "total_lines": total_lines,
        "requested_line_count": requested_count,
        "content": "".join(selected),
        "sha256": snapshot.sha256,
        "warnings": warnings,
    }


def search_content(
    path: str,
    *,
    workspace: str,
    query: str,
    regex: bool = False,
    case_sensitive: bool = False,
    glob: str | None = None,
    output_mode: str = "content",
    max_results: int = 20,
    offset: int = 0,
    context_lines: int = 2,
) -> dict[str, Any]:
    if not query:
        raise PartialFileOperationError("query가 비어 있습니다.")
    mode = output_mode or "content"
    if mode not in {"content", "files_with_matches", "count"}:
        raise PartialFileOperationError("output_mode는 content, files_with_matches, count 중 하나여야 합니다.")
    max_results = max(1, min(int(max_results or 20), MAX_SEARCH_RESULTS))
    offset = max(0, int(offset or 0))
    context_lines = max(0, min(int(context_lines or 0), 20))
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(query if regex else re.escape(query), flags)

    total_match_count = 0
    skipped_files: list[str] = []
    matches: list[dict[str, Any]] = []
    files_with_matches: list[str] = []

    for file_path in _candidate_files(path, workspace=workspace, glob=glob):
        workspace_path = _workspace_path_from_full(workspace, file_path)
        try:
            snapshot = read_text_snapshot(file_path)
        except PartialFileOperationError:
            skipped_files.append(workspace_path)
            continue
        file_matches = _search_snapshot(
            snapshot,
            pattern,
            workspace_path=workspace_path,
            context_lines=context_lines,
            collect=mode == "content",
        )
        if not file_matches:
            continue
        files_with_matches.append(workspace_path)
        total_match_count += len(file_matches)
        if mode == "content":
            matches.extend(file_matches)

    if mode == "count":
        return {
            "match_count": total_match_count,
            "file_count": len(files_with_matches),
            "skipped_files": skipped_files,
        }
    if mode == "files_with_matches":
        paged = files_with_matches[offset: offset + max_results]
        return {
            "files": paged,
            "total_files": len(files_with_matches),
            "offset": offset,
            "truncated": offset + max_results < len(files_with_matches),
            "skipped_files": skipped_files,
        }

    paged_matches = matches[offset: offset + max_results]
    return {
        "matches": paged_matches,
        "total_matches": len(matches),
        "offset": offset,
        "truncated": offset + max_results < len(matches),
        "skipped_files": skipped_files,
    }


def edit_text(
    path: str,
    *,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    if old_string == "":
        raise PartialFileOperationError("old_string은 비어 있을 수 없습니다.")
    if old_string == new_string:
        raise PartialFileOperationError("old_string과 new_string이 같아 변경할 내용이 없습니다.")
    snapshot = read_text_snapshot(path)
    _assert_expected_sha(snapshot, expected_sha256)
    matched_count = snapshot.text.count(old_string)
    if matched_count == 0:
        raise PartialFileOperationError("old_string을 파일에서 찾지 못했습니다.")
    if matched_count > 1 and not replace_all:
        raise PartialFileOperationError("old_string이 여러 번 매칭됩니다. 주변 문맥을 포함하거나 replace_all=true를 사용하세요.")

    replace_count = matched_count if replace_all else 1
    new_text = snapshot.text.replace(old_string, new_string, replace_count)
    return _change_result(
        snapshot,
        new_text,
        matched_count=matched_count,
        replaced_count=replace_count,
    )


def append_text(
    path: str,
    *,
    content: str,
    ensure_newline: bool = True,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    snapshot = read_text_snapshot(path)
    _assert_expected_sha(snapshot, expected_sha256)
    insertion = content
    if ensure_newline and snapshot.text and not snapshot.text.endswith(("\n", "\r")):
        insertion = "\n" + insertion
    new_text = snapshot.text + insertion
    result = _change_result(snapshot, new_text)
    result["appended_chars"] = len(insertion)
    return result


def replace_range(
    path: str,
    *,
    start_line: int,
    end_line: int,
    content: str,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    if start_line < 1:
        raise PartialFileOperationError("start_line은 1 이상이어야 합니다.")
    if end_line < start_line:
        raise PartialFileOperationError("end_line은 start_line 이상이어야 합니다.")
    snapshot = read_text_snapshot(path)
    _assert_expected_sha(snapshot, expected_sha256)
    lines = snapshot.text.splitlines(keepends=True)
    total_lines = len(snapshot.text.splitlines()) if snapshot.text else 0
    if total_lines == 0:
        raise PartialFileOperationError("빈 파일에는 줄 범위 교체를 사용할 수 없습니다.")
    if end_line > total_lines:
        raise PartialFileOperationError("교체 범위가 파일 끝을 넘어갑니다.")
    start_index = start_line - 1
    end_index = end_line
    new_text = "".join([*lines[:start_index], content, *lines[end_index:]])
    result = _change_result(snapshot, new_text)
    result.update({
        "replaced_start_line": start_line,
        "replaced_end_line": end_line,
        "old_line_count": end_line - start_line + 1,
        "new_line_count": len(content.splitlines()) if content else 0,
    })
    return result


def _stats_for_text(raw: bytes, text: str, sha: str) -> dict[str, Any]:
    words = len(re.findall(r"\S+", text))
    return {
        "bytes": len(raw),
        "chars": len(text),
        "chars_no_whitespace": len(re.sub(r"\s+", "", text)),
        "lines": len(text.splitlines()) if text else 0,
        "words": words,
        "korean_eojeol_estimate": words,
        "estimated_speech_minutes": {
            "slow": _estimate_minutes(words, 110),
            "normal": _estimate_minutes(words, 140),
            "fast": _estimate_minutes(words, 170),
        },
        "sha256": sha,
    }


def _estimate_minutes(words: int, per_minute: int) -> int:
    return 0 if words <= 0 else math.ceil(words / per_minute)


def _assert_expected_sha(snapshot: TextSnapshot, expected_sha256: str | None) -> None:
    if expected_sha256 and expected_sha256 != snapshot.sha256:
        raise ChecksumMismatchError("expected_sha256이 현재 파일 checksum과 일치하지 않습니다.")


def _change_result(snapshot: TextSnapshot, new_text: str, **extra: Any) -> dict[str, Any]:
    raw = new_text.encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    old_lines = snapshot.text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )
    result = {
        "new_content": new_text,
        "old_stats": snapshot.stats,
        "new_stats": _stats_for_text(raw, new_text, sha),
        "sha256": sha,
        "old_sha256": snapshot.sha256,
        "diff_preview": diff[:MAX_DIFF_CHARS],
        "diff_truncated": len(diff) > MAX_DIFF_CHARS,
    }
    result.update(extra)
    return result


def _candidate_files(path: str, *, workspace: str, glob: str | None) -> list[str]:
    if os.path.isfile(path):
        if glob and not fnmatch.fnmatch(os.path.basename(path), glob):
            return []
        return [path]
    if not os.path.isdir(path):
        raise PartialFileOperationError("파일 또는 디렉토리가 없습니다.")

    files: list[str] = []
    for root, dirnames, filenames in os.walk(path):
        dirnames[:] = [name for name in dirnames if name not in SKIPPED_DIRS]
        for filename in filenames:
            if filename in SKIPPED_FILE_NAMES:
                continue
            if glob and not fnmatch.fnmatch(filename, glob):
                continue
            file_path = os.path.realpath(os.path.join(root, filename))
            try:
                inside_workspace = os.path.commonpath([os.path.realpath(workspace), file_path]) == os.path.realpath(workspace)
            except ValueError:
                inside_workspace = False
            if inside_workspace:
                files.append(file_path)
    return files


def _search_snapshot(
    snapshot: TextSnapshot,
    pattern: re.Pattern[str],
    *,
    workspace_path: str,
    context_lines: int,
    collect: bool,
) -> list[dict[str, Any]]:
    lines = snapshot.text.splitlines()
    matches: list[dict[str, Any]] = []
    for line_index, line in enumerate(lines):
        for match in pattern.finditer(line):
            if not collect:
                matches.append({"path": workspace_path})
                continue
            start = max(0, line_index - context_lines)
            end = min(len(lines), line_index + context_lines + 1)
            matches.append({
                "path": workspace_path,
                "line": line_index + 1,
                "column": match.start() + 1,
                "preview": line.strip(),
                "context": lines[start:end],
            })
    return matches


def _workspace_path_from_full(workspace: str, full_path: str) -> str:
    relative = os.path.relpath(full_path, workspace).replace("\\", "/")
    return "/" if relative == "." else f"/{relative}"
