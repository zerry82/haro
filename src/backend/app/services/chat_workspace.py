from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.services.harness import normalize_workspace_path
from app.services.workspace_file_db import record_workspace_relation, sync_workspace_subtree

CHAT_KEEP_RECENT_MESSAGES = 20
CHAT_SUMMARY_SUGGEST_MESSAGE_COUNT = 40
CHAT_AREA_ALIASES = {"inputs", "working", "outputs", "summaries"}
WORKSPACE_ROOT_PREFIXES = ("/playground/", "/clean-room/", "/90_archive/", "/.haro/")


def ensure_chat_workspace(workspace: str, user_id: str, chat: ChatSession) -> str:
    """Create the on-disk chat workspace and return its workspace-relative path."""
    if not chat.folder_path:
        chat.folder_path = _default_chat_folder_path(user_id, chat)

    folder_path = normalize_workspace_path(chat.folder_path)
    chat.folder_path = folder_path

    full_dir = _full_path(workspace, folder_path)
    for relative in ("inputs", "working", "outputs", "summaries"):
        os.makedirs(os.path.join(full_dir, relative), exist_ok=True)

    _ensure_text_file(workspace, folder_path, "README.md", _readme_template(chat))
    _ensure_text_file(workspace, folder_path, "conversation.md", "# Conversation\n\n")
    _ensure_text_file(workspace, folder_path, "context.md", _context_template(chat))
    _ensure_text_file(workspace, folder_path, "decisions.md", "# Decisions\n\n")
    _ensure_text_file(workspace, folder_path, "rule-candidates.md", "# Rule Candidates\n\n")
    _ensure_text_file(workspace, folder_path, "agent-log.md", "# Agent Log\n\n")
    _ensure_json_file(workspace, folder_path, "linked-files.json", {
        "inputs": [],
        "derived": [],
        "outputs": [],
        "exports": [],
    })
    _ensure_json_file(workspace, folder_path, "artifacts.json", {"artifacts": []})
    _ensure_json_file(workspace, f"{folder_path}/summaries", "index.json", {"summaries": []})
    sync_workspace_subtree(workspace, folder_path, source_kind="chat", chat_id=chat.id)
    return folder_path


def get_chat_default_write_path(chat: ChatSession, requested: str | None, tool_name: str) -> str:
    """Resolve implicit write paths into the current chat workspace.

    Absolute paths under known workspace roots are treated as explicit. A bare
    filename such as `report.md`, or `/report.md`, is treated as implicit.
    Chat area aliases such as `outputs/report.md` are resolved once under the
    current chat folder to avoid paths like `outputs/outputs/report.md`.
    """
    requested = (requested or "").replace("\\", "/").strip()
    if _is_explicit_workspace_path(requested):
        return normalize_workspace_path(requested)

    name = requested.lstrip("/") or ("new-folder" if tool_name == "dir_create" else "output.md")
    parts = [part for part in name.split("/") if part]
    if len(parts) > 1 and parts[0] in CHAT_AREA_ALIASES:
        area = parts[0]
        safe_name = "/".join(_safe_segment(part, "untitled") for part in parts[1:])
        return normalize_workspace_path(f"{chat.folder_path}/{area}/{safe_name}")

    safe_name = "/".join(_safe_segment(part, "untitled") for part in parts)
    area = "working" if tool_name == "dir_create" else "outputs"
    return normalize_workspace_path(f"{chat.folder_path}/{area}/{safe_name}")


def is_summary_suggested(message_count: int) -> bool:
    return message_count >= CHAT_SUMMARY_SUGGEST_MESSAGE_COUNT


def append_conversation_message(workspace: str, chat: ChatSession, role: str, content: str, created_at: str | None = None) -> None:
    if not chat.folder_path:
        return
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    label = "사용자" if role == "user" else "haro"
    entry = f"## {timestamp} {label}\n\n{content.strip()}\n\n"
    _append_text(workspace, chat.folder_path, "conversation.md", entry)


def append_agent_log(workspace: str, chat: ChatSession, event_type: str, content: str) -> None:
    if not chat.folder_path:
        return
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"## {timestamp} {event_type}\n\n```text\n{content.strip()}\n```\n\n"
    _append_text(workspace, chat.folder_path, "agent-log.md", entry)


def record_file_reference(
    workspace: str,
    chat: ChatSession,
    kind: str,
    path: str,
    *,
    action: str | None = None,
    target_path: str | None = None,
) -> None:
    if not chat.folder_path:
        return
    linked = _load_json_file(workspace, chat.folder_path, "linked-files.json", {
        "inputs": [],
        "derived": [],
        "outputs": [],
        "exports": [],
    })
    for key in ("inputs", "derived", "outputs", "exports"):
        linked.setdefault(key, [])
    normalized = normalize_workspace_path(path)

    if kind == "exports":
        entry = {
            "source_path": normalized,
            "target_path": normalize_workspace_path(target_path),
            "action": action or "exported",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        if entry not in linked["exports"]:
            linked["exports"].append(entry)
        record_workspace_relation(
            workspace,
            "exported_to",
            from_path=normalized,
            to_path=entry["target_path"],
            chat_id=chat.id,
        )
    else:
        entry = {"path": normalized, "action": action or kind}
        if entry not in linked[kind]:
            linked[kind].append(entry)
        relation_type = "chat_input" if kind == "inputs" else "chat_output" if kind == "outputs" else "derived_from"
        if relation_type == "chat_input":
            record_workspace_relation(workspace, relation_type, from_path=normalized, to_path=chat.folder_path, chat_id=chat.id)
        else:
            record_workspace_relation(workspace, relation_type, from_path=chat.folder_path, to_path=normalized, chat_id=chat.id)

    _write_json_file(workspace, chat.folder_path, "linked-files.json", linked)


def record_preview_reference(
    workspace: str,
    chat: ChatSession,
    url: str,
    *,
    ip: str | None = None,
    action: str | None = None,
) -> None:
    if not chat.folder_path:
        return
    linked = _load_json_file(workspace, chat.folder_path, "linked-files.json", {
        "inputs": [],
        "derived": [],
        "outputs": [],
        "exports": [],
        "previews": [],
    })
    for key in ("inputs", "derived", "outputs", "exports", "previews"):
        linked.setdefault(key, [])

    entry = {
        "url": url,
        "ip": ip,
        "action": action or "preview_ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    linked["previews"].append(entry)
    _write_json_file(workspace, chat.folder_path, "linked-files.json", linked)


def get_latest_chat_output_reference(workspace: str, chat: ChatSession | None) -> dict | None:
    if not chat or not chat.folder_path:
        return None
    linked = _load_json_file(workspace, chat.folder_path, "linked-files.json", {
        "inputs": [],
        "derived": [],
        "outputs": [],
        "exports": [],
    })
    outputs = linked.get("outputs") or []
    if outputs:
        latest = outputs[-1]
        path = latest.get("path")
        if path:
            return {
                "kind": "outputs",
                "path": normalize_workspace_path(path),
                "action": latest.get("action"),
            }
    exports = linked.get("exports") or []
    if exports:
        latest = exports[-1]
        path = latest.get("target_path") or latest.get("source_path")
        if path:
            return {
                "kind": "exports",
                "path": normalize_workspace_path(path),
                "action": latest.get("action"),
            }
    return None


def get_latest_chat_preview_reference(workspace: str, chat: ChatSession | None) -> dict | None:
    if not chat or not chat.folder_path:
        return None
    linked = _load_json_file(workspace, chat.folder_path, "linked-files.json", {
        "inputs": [],
        "derived": [],
        "outputs": [],
        "exports": [],
        "previews": [],
    })
    previews = linked.get("previews") or []
    if not previews:
        return None
    latest = previews[-1]
    url = latest.get("url")
    if not url:
        return None
    return {
        "kind": "preview",
        "url": str(url),
        "ip": latest.get("ip"),
        "action": latest.get("action"),
    }


def export_chat_file(workspace: str, chat: ChatSession, source_path: str, target_path: str) -> str:
    source = normalize_workspace_path(source_path)
    target = normalize_workspace_path(target_path)
    source_full = _full_path(workspace, source)
    target_full = _full_path(workspace, target)
    if not os.path.isfile(source_full):
        raise FileNotFoundError(f"Source file not found: {source}")
    os.makedirs(os.path.dirname(target_full), exist_ok=True)
    shutil.copy2(source_full, target_full)
    record_file_reference(workspace, chat, "exports", source, target_path=target)
    sync_workspace_subtree(workspace, target, source_kind="chat", chat_id=chat.id)
    return target


async def sync_chat_workspace_files(db: AsyncSession, workspace: str, user_id: str, chat: ChatSession) -> str:
    folder_path = ensure_chat_workspace(workspace, user_id, chat)

    messages = (await db.execute(
        select(Message).where(Message.chat_session_id == chat.id).order_by(Message.created_at.asc())
    )).scalars().all()
    conversation = ["# Conversation\n\n"]
    for message in messages:
        label = "사용자" if message.role == "user" else "haro"
        conversation.append(f"## {message.created_at} {label}\n\n{message.content.strip()}\n\n")
    _write_text_file(workspace, folder_path, "conversation.md", "".join(conversation))

    logs = (await db.execute(
        select(AgentLog).where(AgentLog.chat_session_id == chat.id).order_by(AgentLog.created_at.asc())
    )).scalars().all()
    agent_log = ["# Agent Log\n\n"]
    for log in logs:
        agent_log.append(f"## {log.created_at} {log.event_type}\n\n```text\n{log.content.strip()}\n```\n\n")
    _write_text_file(workspace, folder_path, "agent-log.md", "".join(agent_log))
    sync_workspace_subtree(workspace, folder_path, source_kind="chat", chat_id=chat.id)
    return folder_path


async def summarize_chat_workspace(db: AsyncSession, workspace: str, user_id: str, chat: ChatSession) -> dict:
    folder_path = ensure_chat_workspace(workspace, user_id, chat)
    messages = (await db.execute(
        select(Message)
        .where(Message.chat_session_id == chat.id, Message.compressed == False)
        .order_by(Message.created_at.asc())
    )).scalars().all()

    if not messages:
        return {"summary_path": None, "context_path": f"{folder_path}/context.md", "compressed_message_count": 0}

    if len(messages) > CHAT_KEEP_RECENT_MESSAGES:
        source_messages = messages[:-CHAT_KEEP_RECENT_MESSAGES]
    else:
        source_messages = messages

    next_index = _next_summary_index(workspace, folder_path)
    summary_name = f"summary-{next_index:04d}.md"
    summary_path = f"{folder_path}/summaries/{summary_name}"
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = _build_summary_markdown(chat, source_messages, next_index, generated_at)
    _write_text_file(workspace, f"{folder_path}/summaries", summary_name, summary)

    index = _load_json_file(workspace, f"{folder_path}/summaries", "index.json", {"summaries": []})
    index["summaries"].append({
        "path": summary_path,
        "message_count": len(source_messages),
        "generated_at": generated_at,
    })
    _write_json_file(workspace, f"{folder_path}/summaries", "index.json", index)

    compressed_count = 0
    if len(messages) > CHAT_KEEP_RECENT_MESSAGES:
        for message in source_messages:
            message.compressed = True
            compressed_count += 1

    _write_text_file(workspace, folder_path, "context.md", _build_context_markdown(chat, index["summaries"], workspace))
    sync_workspace_subtree(workspace, folder_path, source_kind="chat", chat_id=chat.id)
    chat.updated_at = generated_at
    await db.commit()

    return {
        "summary_path": summary_path,
        "context_path": f"{folder_path}/context.md",
        "compressed_message_count": compressed_count,
    }


def load_chat_context(workspace: str, chat: ChatSession | None) -> str | None:
    if not chat or not chat.folder_path:
        return None
    sections: list[str] = []
    for name in ("context.md", "decisions.md", "rule-candidates.md", "linked-files.json"):
        path = _full_path(workspace, f"{chat.folder_path}/{name}")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read().strip()
        if content:
            sections.append(f"## {name}\n{content}")
    return "\n\n".join(sections) if sections else None


def _default_chat_folder_path(user_id: str, chat: ChatSession) -> str:
    date = (chat.created_at or datetime.now(timezone.utc).isoformat())[:10]
    slug = _safe_segment(chat.title, "chat")
    return f"/playground/users/{user_id}/50_chats/{date}-{slug}-{chat.id[:8]}"


def _safe_segment(value: str | None, fallback: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip(" .-")
    return (value or fallback)[:80]


def _is_explicit_workspace_path(path: str) -> bool:
    normalized = normalize_workspace_path(path)
    if not normalized.startswith("/"):
        return False
    return any(normalized.startswith(prefix) for prefix in WORKSPACE_ROOT_PREFIXES)


def _readme_template(chat: ChatSession) -> str:
    return f"""# {chat.title}

status: active
created_at: {chat.created_at}
last_activity_at: {chat.updated_at}
chat_id: {chat.id}

## 목적

이 채팅에서 진행하는 작업의 목적을 기록합니다.

## 현재 상태

- 아직 정리된 상태가 없습니다.

## 주요 산출물

- 아직 연결된 산출물이 없습니다.
"""


def _context_template(chat: ChatSession) -> str:
    return f"""# Current Chat Context

chat_id: {chat.id}
updated_at: {datetime.now(timezone.utc).isoformat()}

아직 압축된 맥락이 없습니다.
"""


def _build_summary_markdown(chat: ChatSession, messages: Iterable[Message], index: int, generated_at: str) -> str:
    lines = [
        f"# Chat Summary {index:04d}",
        "",
        f"chat_id: {chat.id}",
        f"generated_at: {generated_at}",
        "",
        "## 핵심 대화",
        "",
    ]
    for message in messages:
        label = "사용자" if message.role == "user" else "haro"
        text = " ".join(message.content.strip().split())
        if len(text) > 420:
            text = f"{text[:420]}..."
        lines.append(f"- {message.created_at} {label}: {text}")
    lines.append("")
    return "\n".join(lines)


def _build_context_markdown(chat: ChatSession, summaries: list[dict], workspace: str) -> str:
    lines = [
        "# Current Chat Context",
        "",
        f"chat_id: {chat.id}",
        f"updated_at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## 누적 요약",
        "",
    ]
    if not summaries:
        lines.append("아직 압축된 맥락이 없습니다.")
    for item in summaries[-5:]:
        path = item.get("path")
        if not path:
            continue
        full = _full_path(workspace, path)
        if not os.path.isfile(full):
            continue
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            lines.append(f.read().strip())
            lines.append("")
    return "\n".join(lines)


def _next_summary_index(workspace: str, folder_path: str) -> int:
    index = _load_json_file(workspace, f"{folder_path}/summaries", "index.json", {"summaries": []})
    return len(index.get("summaries", [])) + 1


def _ensure_text_file(workspace: str, folder_path: str, name: str, content: str) -> None:
    full = _full_path(workspace, f"{folder_path}/{name}")
    if os.path.exists(full):
        return
    _write_text_file(workspace, folder_path, name, content)


def _ensure_json_file(workspace: str, folder_path: str, name: str, content: dict) -> None:
    full = _full_path(workspace, f"{folder_path}/{name}")
    if os.path.exists(full):
        return
    _write_json_file(workspace, folder_path, name, content)


def _append_text(workspace: str, folder_path: str, name: str, content: str) -> None:
    full = _full_path(workspace, f"{folder_path}/{name}")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "a", encoding="utf-8") as f:
        f.write(content)


def _write_text_file(workspace: str, folder_path: str, name: str, content: str) -> None:
    full = _full_path(workspace, f"{folder_path}/{name}")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _load_json_file(workspace: str, folder_path: str, name: str, fallback: dict) -> dict:
    full = _full_path(workspace, f"{folder_path}/{name}")
    if not os.path.isfile(full):
        return json.loads(json.dumps(fallback))
    try:
        with open(full, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return json.loads(json.dumps(fallback))


def _write_json_file(workspace: str, folder_path: str, name: str, content: dict) -> None:
    full = _full_path(workspace, f"{folder_path}/{name}")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _full_path(workspace: str, requested: str) -> str:
    normalized = normalize_workspace_path(requested)
    workspace_real = os.path.realpath(workspace)
    full = os.path.realpath(os.path.join(workspace_real, normalized.lstrip("/")))
    if os.path.commonpath([workspace_real, full]) != workspace_real:
        raise PermissionError("워크스페이스 외부 접근 불가")
    return full
