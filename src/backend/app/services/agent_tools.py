from __future__ import annotations

"""Tool execution helpers for the chat agent."""

import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.project import Project
from app.services.chat_workspace import (
    append_agent_log,
    export_chat_file,
    get_chat_default_write_path,
    record_file_reference,
    record_preview_reference,
)
from app.services.chat_workspace_paths import ResultPathRequiredError
from app.services.file_path_policy import assert_read_allowed, assert_write_allowed
from app.services.workspace_aliases import resolve_workspace_alias_path
from app.services.sse import SSEEmitter
from app.services.workspace_file_db import (
    WorkspaceSearchUnavailable,
    atomic_write_text,
    count_workspace_items,
    list_workspace_directory,
    mark_workspace_summary_stale,
    search_workspace_files,
    sync_workspace_path,
)
from app.services.workspace_index import update_file_summary
from app.services.web_search import (
    WebSearchProviderError,
    WebSearchTimeoutError,
    WebSearchUnavailableError,
    search_web,
)


def _validate_path(workspace: str, requested: str) -> str:
    full = os.path.realpath(os.path.join(workspace, requested.lstrip("/")))
    if not full.startswith(os.path.realpath(workspace)):
        raise PermissionError("워크스페이스 외부 접근 불가")
    return full


def _assert_tool_read_allowed(path: str, user_id: str | None = None) -> None:
    assert_read_allowed(path, user_id)


def _assert_tool_write_allowed(path: str, user_id: str | None = None) -> None:
    assert_write_allowed(path, user_id)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "recursive"}
    return bool(value)


async def execute_tool(
    workspace: str,
    tool_name: str,
    args: dict,
    emitter: SSEEmitter,
    db: AsyncSession | None = None,
    project: Project | None = None,
    chat_session: ChatSession | None = None,
) -> str:
    """Run a selected agent tool and emit workspace updates."""
    try:
        if tool_name == "code_run":
            if db is None or project is None:
                return "도구 실행 에러: code_run requires sandbox context"
            from app.services.container_manager import ContainerManager

            cm = ContainerManager(db)
            filename = args.get("filename", "script.ts")
            code = args.get("code", "")
            result = await cm.execute_code(project.id, filename, code)
            output_parts = []
            if result["stdout"]:
                output_parts.append(f"[stdout]\n{result['stdout']}")
            if result["stderr"]:
                output_parts.append(f"[stderr]\n{result['stderr']}")
            output_parts.append(f"[exit_code: {result['exit_code']}]")
            return "\n".join(output_parts)

        if tool_name == "web_preview":
            if db is None or project is None:
                return "도구 실행 에러: web_preview requires sandbox context"
            from app.services.container_manager import ContainerManager

            cm = ContainerManager(db)
            ip = await cm.start_preview(project.id)
            preview_url = f"/preview/{project.id}/"
            emitter.emit("preview_ready", {"url": preview_url, "ip": ip})
            if chat_session:
                record_preview_reference(workspace, chat_session, preview_url, ip=ip)
                append_agent_log(workspace, chat_session, "web_preview", preview_url)
            return f"웹 프리뷰 시작됨. URL: {preview_url}"

        if tool_name == "file_export":
            if chat_session is None:
                return "도구 실행 에러: file_export requires chat context"
            user_id = project.user_id if project else None
            source_path = _resolve_tool_path(args.get("source_path", ""), user_id)
            target_path = _resolve_tool_path(args.get("target_path", ""), user_id)
            _assert_tool_read_allowed(source_path, user_id)
            _assert_tool_write_allowed(target_path, user_id)
            exported_path = export_chat_file(workspace, chat_session, source_path, target_path)
            emitter.emit("file_changed", {"action": "created", "path": exported_path, "type": "file"})
            await update_file_summary(workspace, exported_path, "created")
            append_agent_log(workspace, chat_session, "file_export", f"{source_path} -> {exported_path}")
            return f"파일 내보내기 완료: {source_path} -> {exported_path}"

        if tool_name == "web_search":
            return await _execute_web_search(args)

        user_id = project.user_id if project else None
        path = _resolve_tool_path(args.get("path", "/"), user_id)
        if tool_name == "file_search":
            query = args.get("query") or args.get("q") or ""
            limit = int(args.get("limit") or 10)
            try:
                items = search_workspace_files(
                    workspace,
                    query,
                    item_type=args.get("item_type") or args.get("type"),
                    room=args.get("room"),
                    access_policy=args.get("access_policy"),
                    chat_id=args.get("chat_id"),
                    limit=max(1, min(limit, 20)),
                )
            except WorkspaceSearchUnavailable:
                return "파일 검색을 사용할 수 없습니다: workspace DB 검색 인덱스가 준비되지 않았습니다."
            if not items:
                return f"검색 결과 없음: {query}"
            lines = [f"검색 결과 ({query}):"]
            for item in items:
                snippet = f" — {item['summary_snippet']}" if item.get("summary_snippet") else ""
                lines.append(f"- {item['path']} ({item['item_type']}, {item['language']}){snippet}")
            return "\n".join(lines)

        if tool_name == "file_count":
            item_type = args.get("item_type") or args.get("type")
            recursive = _as_bool(args.get("recursive", False))
            _assert_tool_read_allowed(path, user_id)
            full_path = _validate_path(workspace, path)
            if not os.path.isdir(full_path):
                return f"디렉토리 없음: {path}"
            count = count_workspace_items(
                workspace,
                path,
                item_type=item_type,
                recursive=recursive,
                room=args.get("room"),
                access_policy=args.get("access_policy"),
                chat_id=args.get("chat_id"),
            )
            type_label = "항목"
            if str(item_type).lower() in {"dir", "directory", "folder", "folders"}:
                type_label = "폴더"
            elif str(item_type).lower() in {"file", "files"}:
                type_label = "파일"
            scope = "하위 전체" if recursive else "직속"
            return f"{path}의 {scope} {type_label} 수: {count}"

        if chat_session and tool_name in {"file_create", "file_write", "dir_create"}:
            path = get_chat_default_write_path(chat_session, path, tool_name, user_id)
        _assert_tool_read_allowed(path, user_id)
        full_path = _validate_path(workspace, path)

        if tool_name == "file_create":
            _assert_tool_write_allowed(path, user_id)
            os.makedirs(os.path.dirname(full_path) or full_path, exist_ok=True)
            atomic_write_text(full_path, args.get("content", ""))
            emitter.emit("file_changed", {"action": "created", "path": path, "type": "file"})
            await update_file_summary(workspace, path, "created")
            if chat_session:
                record_file_reference(workspace, chat_session, "outputs", path, action="created")
                append_agent_log(workspace, chat_session, "file_create", path)
            return f"파일 생성 완료: {path}"

        if tool_name == "file_read":
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            if chat_session:
                record_file_reference(workspace, chat_session, "inputs", path, action="read")
            return content

        if tool_name == "file_write":
            _assert_tool_write_allowed(path, user_id)
            atomic_write_text(full_path, args.get("content", ""))
            mark_workspace_summary_stale(workspace, path)
            emitter.emit("file_changed", {"action": "modified", "path": path, "type": "file"})
            await update_file_summary(workspace, path, "modified")
            if chat_session:
                record_file_reference(workspace, chat_session, "outputs", path, action="modified")
                append_agent_log(workspace, chat_session, "file_write", path)
            return f"파일 수정 완료: {path}"

        if tool_name == "file_delete":
            _assert_tool_write_allowed(path, user_id)
            os.remove(full_path)
            emitter.emit("file_changed", {"action": "deleted", "path": path, "type": "file"})
            await update_file_summary(workspace, path, "deleted")
            if chat_session:
                append_agent_log(workspace, chat_session, "file_delete", path)
            return f"파일 삭제 완료: {path}"

        if tool_name == "dir_list":
            if not os.path.isdir(full_path):
                return f"디렉토리 없음: {path}"
            items = list_workspace_directory(workspace, path)
            dir_count = sum(1 for item in items if item["type"] == "directory")
            file_count = len(items) - dir_count
            lines = []
            for item in items:
                t = "dir" if item["type"] == "directory" else "file"
                suffix = ""
                if item["type"] == "directory" and item.get("children_count") is not None:
                    suffix = f" ({item['children_count']}개 항목)"
                lines.append(f"  [{t}] {item['name']}{suffix}")
            if not lines:
                return f"빈 디렉토리: {path}"
            return f"디렉토리 목록 ({path}, 폴더 {dir_count}개, 파일 {file_count}개):\n" + "\n".join(lines)

        if tool_name == "dir_create":
            _assert_tool_write_allowed(path, user_id)
            os.makedirs(full_path, exist_ok=True)
            sync_workspace_path(workspace, path, source_kind="agent", chat_id=chat_session.id if chat_session else None)
            emitter.emit("file_changed", {"action": "created", "path": path, "type": "directory"})
            if chat_session:
                append_agent_log(workspace, chat_session, "dir_create", path)
            return f"디렉토리 생성 완료: {path}"

        return f"알 수 없는 도구: {tool_name}"

    except ResultPathRequiredError as e:
        return str(e)
    except Exception as e:
        return f"도구 실행 에러: {str(e)}"


def _resolve_tool_path(path: object, user_id: str | None) -> str:
    value = str(path or "")
    if not user_id:
        return value
    return resolve_workspace_alias_path(value, user_id)


async def _execute_web_search(args: dict) -> str:
    query = " ".join(str(args.get("query") or args.get("q") or "").split())
    if not query:
        return "웹 검색을 실행할 수 없습니다: query가 비어 있습니다."
    try:
        limit = int(args.get("limit") or 5)
    except Exception:
        limit = 5
    try:
        recency_days = int(args["recency_days"]) if args.get("recency_days") is not None else None
    except Exception:
        recency_days = None
    domains = args.get("domains") if isinstance(args.get("domains"), list) else None

    try:
        results = await search_web(query, limit=limit, recency_days=recency_days, domains=domains)
    except ValueError as exc:
        return f"웹 검색을 실행할 수 없습니다: {exc}"
    except WebSearchUnavailableError as exc:
        return f"웹 검색을 사용할 수 없습니다: {exc}"
    except WebSearchTimeoutError:
        return "웹 검색 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
    except WebSearchProviderError as exc:
        return f"웹 검색 제공자 오류: {exc}"

    if not results:
        return f"웹 검색 결과 없음: {query}"

    lines = [f"웹 검색 결과 ({query}):"]
    for index, result in enumerate(results, start=1):
        lines.append(f"{index}. {result.title}")
        lines.append(f"   URL: {result.url}")
        if result.snippet:
            lines.append(f"   요약: {result.snippet}")
        if result.published_at:
            lines.append(f"   날짜: {result.published_at}")
        if result.source:
            lines.append(f"   출처: {result.source}")
    return "\n".join(lines)
