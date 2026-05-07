from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.services.chat_workspace_files import load_json_file, write_json_file, write_text_file
from app.services.chat_workspace_lifecycle import ensure_chat_workspace
from app.services.chat_workspace_paths import full_path
from app.services.workspace_file_db import sync_workspace_subtree

CHAT_KEEP_RECENT_MESSAGES = 20
CHAT_SUMMARY_SUGGEST_MESSAGE_COUNT = 40


def is_summary_suggested(message_count: int) -> bool:
    return message_count >= CHAT_SUMMARY_SUGGEST_MESSAGE_COUNT


async def sync_chat_workspace_files(db: AsyncSession, workspace: str, user_id: str, chat: ChatSession) -> str:
    folder_path = ensure_chat_workspace(workspace, user_id, chat)

    messages = (await db.execute(
        select(Message).where(Message.chat_session_id == chat.id).order_by(Message.created_at.asc())
    )).scalars().all()
    conversation = ["# Conversation\n\n"]
    for message in messages:
        label = "사용자" if message.role == "user" else "haro"
        conversation.append(f"## {message.created_at} {label}\n\n{message.content.strip()}\n\n")
    write_text_file(workspace, folder_path, "conversation.md", "".join(conversation))

    logs = (await db.execute(
        select(AgentLog).where(AgentLog.chat_session_id == chat.id).order_by(AgentLog.created_at.asc())
    )).scalars().all()
    agent_log = ["# Agent Log\n\n"]
    for log in logs:
        agent_log.append(f"## {log.created_at} {log.event_type}\n\n```text\n{log.content.strip()}\n```\n\n")
    write_text_file(workspace, folder_path, "agent-log.md", "".join(agent_log))
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

    next_index = next_summary_index(workspace, folder_path)
    summary_name = f"summary-{next_index:04d}.md"
    summary_path = f"{folder_path}/summaries/{summary_name}"
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = build_summary_markdown(chat, source_messages, next_index, generated_at)
    write_text_file(workspace, f"{folder_path}/summaries", summary_name, summary)

    index = load_json_file(workspace, f"{folder_path}/summaries", "index.json", {"summaries": []})
    index["summaries"].append({
        "path": summary_path,
        "message_count": len(source_messages),
        "generated_at": generated_at,
    })
    write_json_file(workspace, f"{folder_path}/summaries", "index.json", index)

    compressed_count = 0
    if len(messages) > CHAT_KEEP_RECENT_MESSAGES:
        for message in source_messages:
            message.compressed = True
            compressed_count += 1

    write_text_file(workspace, folder_path, "context.md", build_context_markdown(chat, index["summaries"], workspace))
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
        path = full_path(workspace, f"{chat.folder_path}/{name}")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read().strip()
        if content:
            sections.append(f"## {name}\n{content}")
    return "\n\n".join(sections) if sections else None


def build_summary_markdown(chat: ChatSession, messages: Iterable[Message], index: int, generated_at: str) -> str:
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


def build_context_markdown(chat: ChatSession, summaries: list[dict], workspace: str) -> str:
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
        full = full_path(workspace, path)
        if not os.path.isfile(full):
            continue
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            lines.append(f.read().strip())
            lines.append("")
    return "\n".join(lines)


def next_summary_index(workspace: str, folder_path: str) -> int:
    index = load_json_file(workspace, f"{folder_path}/summaries", "index.json", {"summaries": []})
    return len(index.get("summaries", [])) + 1
