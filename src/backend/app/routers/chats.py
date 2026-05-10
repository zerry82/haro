from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.project import Project
from app.models.user import User
from app.services.chat_workspace import (
    ensure_chat_workspace,
    export_chat_file,
    summarize_chat_workspace,
    sync_chat_workspace_files,
)
from app.services.harness import is_clean_room_path, is_haro_internal_path
from app.services.plan_mode import get_current_plan_session, read_plan_file
from app.services.workspace_file_db import mark_workspace_path_deleted, sync_workspace_subtree
from app.services.workspace_index import update_file_summary

router = APIRouter(prefix="/api/projects/{project_id}/chats", tags=["chats"])


class CreateChatRequest(BaseModel):
    title: str = "새 채팅"


class UpdateChatRequest(BaseModel):
    title: str


class ChatSessionResponse(BaseModel):
    id: str
    project_id: str
    title: str
    folder_path: str | None = None
    created_at: str
    updated_at: str
    message_count: int = 0


class ChatSessionListResponse(BaseModel):
    chats: list[ChatSessionResponse]


class ChatFolderResponse(BaseModel):
    folder_path: str


class ChatSummaryResponse(BaseModel):
    summary_path: str | None
    context_path: str
    compressed_message_count: int


class ChatFileExportRequest(BaseModel):
    source_path: str
    target_path: str


class ChatFileExportResponse(BaseModel):
    source_path: str
    target_path: str


class PlanModeStateResponse(BaseModel):
    active: bool
    plan_session_id: str | None = None
    status: str | None = None
    plan_file_path: str | None = None
    plan_content: str = ""


async def _get_user_project(db: AsyncSession, user_id: str, project_id: str) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _get_chat_session(db: AsyncSession, project_id: str, chat_id: str) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == chat_id, ChatSession.project_id == project_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat


@router.get("", response_model=ChatSessionListResponse)
async def list_chats(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)

    stmt = (
        select(ChatSession, func.count(Message.id).label("msg_count"))
        .outerjoin(Message, Message.chat_session_id == ChatSession.id)
        .where(ChatSession.project_id == project_id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    changed = False
    for chat, _cnt in rows:
        if not chat.folder_path:
            ensure_chat_workspace(project.workspace_path, user.id, chat)
            changed = True
    if changed:
        await db.commit()

    return ChatSessionListResponse(
        chats=[
            ChatSessionResponse(
                id=c.id, project_id=c.project_id, title=c.title, folder_path=c.folder_path,
                created_at=c.created_at, updated_at=c.updated_at,
                message_count=cnt,
            )
            for c, cnt in rows
        ]
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ChatSessionResponse)
async def create_chat(
    project_id: str,
    body: CreateChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    chat = ChatSession(project_id=project.id, title=body.title)
    db.add(chat)
    await db.flush()
    ensure_chat_workspace(project.workspace_path, user.id, chat)

    # Update project updated_at
    project.updated_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    await db.refresh(chat)

    return ChatSessionResponse(
        id=chat.id, project_id=chat.project_id, title=chat.title, folder_path=chat.folder_path,
        created_at=chat.created_at, updated_at=chat.updated_at,
        message_count=0,
    )


@router.patch("/{chat_id}", response_model=ChatSessionResponse)
async def update_chat(
    project_id: str,
    chat_id: str,
    body: UpdateChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    chat = await _get_chat_session(db, project_id, chat_id)
    chat.title = body.title
    chat.updated_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    await db.refresh(chat)

    result = await db.execute(
        select(func.count(Message.id)).where(Message.chat_session_id == chat.id)
    )
    msg_count = result.scalar() or 0

    return ChatSessionResponse(
        id=chat.id, project_id=chat.project_id, title=chat.title, folder_path=chat.folder_path,
        created_at=chat.created_at, updated_at=chat.updated_at,
        message_count=msg_count,
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    project_id: str,
    chat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    chat = await _get_chat_session(db, project_id, chat_id)

    # Check minimum chat constraint
    result = await db.execute(
        select(func.count(ChatSession.id)).where(ChatSession.project_id == project_id)
    )
    chat_count = result.scalar() or 0
    if chat_count <= 1:
        raise HTTPException(
            status_code=400,
            detail="프로젝트에는 최소 하나의 채팅이 있어야 합니다"
        )

    # Delete agent logs and messages for this chat
    await db.execute(delete(AgentLog).where(AgentLog.chat_session_id == chat.id))
    await db.execute(delete(Message).where(Message.chat_session_id == chat.id))
    if chat.folder_path:
        archive_root = os.path.join(project.workspace_path, "90_archive", "chats", user.id)
        os.makedirs(archive_root, exist_ok=True)
        source = os.path.realpath(os.path.join(project.workspace_path, chat.folder_path.lstrip("/")))
        if os.path.isdir(source):
            target = os.path.join(archive_root, os.path.basename(source))
            if os.path.exists(target):
                target = f"{target}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            shutil.move(source, target)
            mark_workspace_path_deleted(project.workspace_path, chat.folder_path, actor_type="user", chat_id=chat.id)
            archive_relative = "/" + os.path.relpath(target, project.workspace_path).replace("\\", "/")
            sync_workspace_subtree(project.workspace_path, archive_relative, source_kind="chat", chat_id=chat.id)
    await db.delete(chat)
    await db.commit()


@router.get("/{chat_id}/folder", response_model=ChatFolderResponse)
async def get_chat_folder(
    project_id: str,
    chat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    chat = await _get_chat_session(db, project_id, chat_id)
    folder_path = ensure_chat_workspace(project.workspace_path, user.id, chat)
    await db.commit()
    return ChatFolderResponse(folder_path=folder_path)


@router.post("/{chat_id}/sync-files", response_model=ChatFolderResponse)
async def sync_chat_files(
    project_id: str,
    chat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    chat = await _get_chat_session(db, project_id, chat_id)
    folder_path = await sync_chat_workspace_files(db, project.workspace_path, user.id, chat)
    await db.commit()
    return ChatFolderResponse(folder_path=folder_path)


@router.get("/{chat_id}/plan-mode", response_model=PlanModeStateResponse)
async def get_plan_mode_state(
    project_id: str,
    chat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    chat = await _get_chat_session(db, project_id, chat_id)
    ensure_chat_workspace(project.workspace_path, user.id, chat)
    plan_session = await get_current_plan_session(db, chat.id)
    if not plan_session:
        return PlanModeStateResponse(active=False)
    return PlanModeStateResponse(
        active=True,
        plan_session_id=plan_session.id,
        status=plan_session.status,
        plan_file_path=plan_session.plan_file_path,
        plan_content=read_plan_file(project.workspace_path, plan_session),
    )


@router.post("/{chat_id}/summarize", response_model=ChatSummaryResponse)
async def summarize_chat(
    project_id: str,
    chat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    chat = await _get_chat_session(db, project_id, chat_id)
    result = await summarize_chat_workspace(db, project.workspace_path, user.id, chat)
    return ChatSummaryResponse(**result)


@router.post("/{chat_id}/files/export", response_model=ChatFileExportResponse)
async def export_chat_artifact(
    project_id: str,
    chat_id: str,
    body: ChatFileExportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    chat = await _get_chat_session(db, project_id, chat_id)
    ensure_chat_workspace(project.workspace_path, user.id, chat)
    if is_haro_internal_path(body.source_path) or is_haro_internal_path(body.target_path):
        raise HTTPException(status_code=403, detail="Haro internal metadata is not accessible")
    if is_clean_room_path(body.target_path):
        raise HTTPException(status_code=403, detail="Clean Room export requires promotion")
    target_path = export_chat_file(project.workspace_path, chat, body.source_path, body.target_path)
    await update_file_summary(project.workspace_path, target_path, "created")
    await db.commit()
    return ChatFileExportResponse(source_path=body.source_path, target_path=target_path)
