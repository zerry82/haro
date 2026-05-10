from __future__ import annotations

"""Tool execution helpers for the chat agent."""

import os
import shutil

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.plan_mode import PlanSession
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
from app.services.plan_mode import (
    PLAN_DRAFTING,
    analyze_plan_requirements,
    plan_file_display_path,
    plan_has_successful_evidence,
    read_plan_file,
    record_plan_event,
    request_plan_approval,
    set_plan_status,
    validate_plan_for_approval,
)
from app.services.workspace_aliases import resolve_workspace_alias_path
from app.services.sse import SSEEmitter
from app.services.workspace_file_db import (
    WorkspaceSearchUnavailable,
    atomic_write_text,
    count_workspace_items,
    list_workspace_directory,
    mark_workspace_path_deleted,
    mark_workspace_summary_stale,
    search_workspace_files,
    sync_workspace_path,
    sync_workspace_subtree,
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


def _workspace_parent_path(path: str) -> str:
    normalized = path.rstrip("/") or "/"
    if normalized == "/":
        return "/"
    parent = os.path.dirname(normalized)
    return parent or "/"


def _workspace_path_from_full(workspace: str, full_path: str) -> str:
    relative = os.path.relpath(full_path, workspace).replace("\\", "/")
    return "/" if relative == "." else f"/{relative}"


def _unique_destination_path(full_path: str) -> str:
    if not os.path.exists(full_path):
        return full_path
    parent = os.path.dirname(full_path)
    basename = os.path.basename(full_path)
    stem, ext = os.path.splitext(basename)
    counter = 1
    while True:
        candidate = os.path.join(parent, f"{stem}_{counter}{ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def _move_workspace_path(workspace: str, source_path: str, target_path: str) -> str:
    source_full = _validate_path(workspace, source_path)
    target_full = _validate_path(workspace, target_path)
    if not os.path.exists(source_full):
        raise FileNotFoundError(f"source path not found: {source_path}")
    if source_path.rstrip("/") == "/":
        raise ValueError("workspace root cannot be moved")
    try:
        moving_into_self = (
            os.path.isdir(source_full)
            and os.path.commonpath([source_full, target_full]) == source_full
        )
    except ValueError:
        moving_into_self = False
    if moving_into_self:
        raise ValueError("cannot move a directory into itself")

    os.makedirs(os.path.dirname(target_full), exist_ok=True)
    if os.path.isdir(source_full) and os.path.isdir(target_full):
        for name in os.listdir(source_full):
            child_source = os.path.join(source_full, name)
            child_target = _unique_destination_path(os.path.join(target_full, name))
            shutil.move(child_source, child_target)
        os.rmdir(source_full)
        return target_path

    final_target = target_full
    if os.path.isdir(target_full):
        final_target = os.path.join(target_full, os.path.basename(source_full))
    final_target = _unique_destination_path(final_target)
    shutil.move(source_full, final_target)
    return _workspace_path_from_full(workspace, final_target)


async def execute_tool(
    workspace: str,
    tool_name: str,
    args: dict,
    emitter: SSEEmitter,
    db: AsyncSession | None = None,
    project: Project | None = None,
    chat_session: ChatSession | None = None,
    plan_session: PlanSession | None = None,
) -> str:
    """Run a selected agent tool and emit workspace updates."""
    try:
        if tool_name == "plan_file_update":
            if db is None or project is None or chat_session is None or plan_session is None:
                return "도구 실행 에러: plan_file_update requires plan context"
            path = plan_session.plan_file_path
            user_id = project.user_id
            _assert_tool_write_allowed(path, user_id)
            full_path = _validate_path(workspace, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            atomic_write_text(full_path, args.get("content", ""))
            mark_workspace_summary_stale(workspace, path)
            emitter.emit("file_changed", {"action": "modified", "path": path, "type": "file"})
            await update_file_summary(workspace, path, "modified")
            display_path = plan_file_display_path(plan_session, user_id)
            requirement_snapshot = analyze_plan_requirements(plan_session, args.get("content", ""))
            payload = {
                "plan_session_id": plan_session.id,
                "plan_file_path": display_path,
                "plan_content": args.get("content", ""),
                "requirements": requirement_snapshot.get("requirements", []),
                "open_questions_clear": requirement_snapshot.get("open_questions_clear", False),
                "evidence_required": requirement_snapshot.get("evidence_required", False),
                "evidence_ledger_has_sources": requirement_snapshot.get("evidence_ledger_has_sources", False),
                "as_of_date": requirement_snapshot.get("as_of_date"),
            }
            emitter.emit("plan_file_updated", payload)
            await record_plan_event(db, plan_session, "plan_file_updated", payload)
            await record_plan_event(db, plan_session, "requirements_extracted", requirement_snapshot)
            if requirement_snapshot.get("open_questions_clear"):
                await set_plan_status(db, plan_session, PLAN_DRAFTING, event_type="requirements_confirmed", payload=requirement_snapshot)
            else:
                await record_plan_event(db, plan_session, "requirements_question_required", requirement_snapshot)
            append_agent_log(workspace, chat_session, "plan_file_update", path)
            return f"계획 파일 수정 완료: {display_path}"

        if tool_name == "plan_approval_request":
            if db is None or project is None or chat_session is None or plan_session is None:
                return "도구 실행 에러: plan_approval_request requires plan context"
            summary = str(args.get("summary") or "계획 승인을 요청합니다.")
            plan_content = read_plan_file(workspace, plan_session)
            has_evidence = await plan_has_successful_evidence(db, plan_session)
            validation = validate_plan_for_approval(plan_session, plan_content, has_successful_evidence=has_evidence)
            if not validation.ok:
                payload = {
                    "plan_session_id": plan_session.id,
                    "reason": validation.reason,
                    "validation": validation.payload or {},
                }
                validation_payload = validation.payload or {}
                if not validation_payload.get("acceptance_checks_present", True):
                    event_type = "acceptance_check_failed"
                elif validation_payload.get("evidence_required"):
                    event_type = "evidence_missing"
                else:
                    event_type = "requirements_question_required"
                await record_plan_event(db, plan_session, event_type, payload)
                emitter.emit("execution_blocked", {"tool": "plan_approval_request", "reason": validation.reason})
                return f"계획 승인 요청 차단: {validation.reason}"
            await request_plan_approval(db, plan_session, summary=summary)
            display_path = plan_file_display_path(plan_session, project.user_id)
            payload = {
                "plan_session_id": plan_session.id,
                "summary": summary,
                "plan_content": plan_content,
                "plan_file_path": display_path,
                "requirements": (validation.payload or {}).get("requirements", []),
                "evidence_required": (validation.payload or {}).get("evidence_required", False),
                "evidence_ledger_has_sources": (validation.payload or {}).get("evidence_ledger_has_sources", False),
                "as_of_date": (validation.payload or {}).get("as_of_date"),
                "acceptance_checks_present": (validation.payload or {}).get("acceptance_checks_present", False),
            }
            emitter.emit("plan_approval_requested", payload)
            append_agent_log(workspace, chat_session, "plan_approval_request", plan_session.plan_file_path)
            return "계획 승인 요청 완료"

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
            result = await _execute_web_search(args)
            if db is not None and plan_session is not None:
                event_type = "evidence_collected" if _is_successful_web_search_result(result) else "evidence_missing"
                await record_plan_event(
                    db,
                    plan_session,
                    event_type,
                    {
                        "query": args.get("query") or args.get("q") or "",
                        "result": result,
                    },
                )
            return result

        user_id = project.user_id if project else None

        if tool_name == "file_move":
            source_path = _resolve_tool_path(
                args.get("source_path") or args.get("from_path") or args.get("src_path") or args.get("path") or "",
                user_id,
            )
            target_path = _resolve_tool_path(
                args.get("target_path") or args.get("to_path") or args.get("dest_path") or "",
                user_id,
            )
            if not source_path or not target_path:
                return "도구 실행 에러: file_move requires source_path and target_path"
            _assert_tool_read_allowed(source_path, user_id)
            _assert_tool_write_allowed(source_path, user_id)
            _assert_tool_write_allowed(target_path, user_id)
            final_target_path = _move_workspace_path(workspace, source_path, target_path)
            mark_workspace_path_deleted(
                workspace,
                source_path,
                actor_type="agent",
                chat_id=chat_session.id if chat_session else None,
            )
            sync_workspace_subtree(
                workspace,
                final_target_path,
                source_kind="agent",
                chat_id=chat_session.id if chat_session else None,
            )
            final_full_path = _validate_path(workspace, final_target_path)
            item_type = "directory" if os.path.isdir(final_full_path) else "file"
            emitter.emit("file_changed", {"action": "deleted", "path": source_path, "type": item_type})
            emitter.emit("file_changed", {"action": "created", "path": final_target_path, "type": item_type})
            await update_file_summary(workspace, source_path, "deleted")
            if os.path.isfile(final_full_path):
                await update_file_summary(workspace, final_target_path, "created")
            if chat_session:
                record_file_reference(workspace, chat_session, "outputs", final_target_path, action="moved")
                append_agent_log(workspace, chat_session, "file_move", f"{source_path} -> {final_target_path}")
            return f"이동 완료: {source_path} -> {final_target_path}"

        if tool_name == "dir_delete":
            path = _resolve_tool_path(args.get("path", ""), user_id)
            if not path:
                return "도구 실행 에러: dir_delete requires path"
            if path.rstrip("/") == "/":
                return "도구 실행 에러: workspace root cannot be deleted"
            _assert_tool_read_allowed(path, user_id)
            _assert_tool_write_allowed(path, user_id)
            full_path = _validate_path(workspace, path)
            if not os.path.isdir(full_path):
                return f"디렉토리 없음: {path}"
            recursive = _as_bool(args.get("recursive", False))
            if not recursive and os.listdir(full_path):
                return f"디렉토리가 비어 있지 않습니다: {path}. recursive=true를 명시해야 삭제할 수 있습니다."
            shutil.rmtree(full_path) if recursive else os.rmdir(full_path)
            mark_workspace_path_deleted(
                workspace,
                path,
                actor_type="agent",
                chat_id=chat_session.id if chat_session else None,
            )
            sync_workspace_path(
                workspace,
                _workspace_parent_path(path),
                source_kind="agent",
                chat_id=chat_session.id if chat_session else None,
            )
            emitter.emit("file_changed", {"action": "deleted", "path": path, "type": "directory"})
            await update_file_summary(workspace, path, "deleted")
            if chat_session:
                append_agent_log(workspace, chat_session, "dir_delete", path)
            return f"디렉토리 삭제 완료: {path}"

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


def _is_successful_web_search_result(result: str) -> bool:
    return result.startswith("웹 검색 결과 (")


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
