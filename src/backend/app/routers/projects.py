from __future__ import annotations

import logging
import os
import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.project import Project
from app.models.user import User
from app.services.container_manager import ContainerManager
from app.services.chat_workspace import ensure_chat_workspace
from app.services.harness import ensure_harness_structure

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    title: str = "새 프로젝트"


class UpdateProjectRequest(BaseModel):
    title: str


class ProjectResponse(BaseModel):
    id: str
    title: str
    status: str
    runtime_mode: str = "work"
    container_status: str = "none"
    created_at: str
    updated_at: str
    chat_session_count: int = 0


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


async def _get_user_project(db: AsyncSession, user_id: str, project_id: str) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=ProjectListResponse)
async def list_projects(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Project, func.count(ChatSession.id).label("chat_count"))
        .outerjoin(ChatSession, ChatSession.project_id == Project.id)
        .where(Project.user_id == user.id)
        .group_by(Project.id)
        .order_by(Project.updated_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return ProjectListResponse(
        projects=[
            ProjectResponse(
                id=p.id, title=p.title, status=p.status,
                runtime_mode=p.runtime_mode,
                container_status=p.container_status,
                created_at=p.created_at, updated_at=p.updated_at,
                chat_session_count=cnt,
            )
            for p, cnt in rows
        ]
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(body: CreateProjectRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pid = str(uuid.uuid4())
    workspace = os.path.join(settings.workspace_root, user.id, pid)
    os.makedirs(workspace, exist_ok=True)
    ensure_harness_structure(workspace, user.id)

    project = Project(id=pid, user_id=user.id, title=body.title, workspace_path=workspace)
    db.add(project)
    await db.flush()

    # Create default chat session
    chat = ChatSession(project_id=pid, title="기본 채팅")
    db.add(chat)
    await db.flush()
    ensure_chat_workspace(workspace, user.id, chat)
    await db.commit()
    await db.refresh(project)

    return ProjectResponse(
        id=project.id, title=project.title, status=project.status,
        runtime_mode=project.runtime_mode,
        container_status=project.container_status,
        created_at=project.created_at, updated_at=project.updated_at,
        chat_session_count=1,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, body: UpdateProjectRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await _get_user_project(db, user.id, project_id)
    project.title = body.title
    project.updated_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    await db.refresh(project)

    # Get chat count
    result = await db.execute(
        select(func.count(ChatSession.id)).where(ChatSession.project_id == project.id)
    )
    chat_count = result.scalar() or 0

    return ProjectResponse(
        id=project.id, title=project.title, status=project.status,
        runtime_mode=project.runtime_mode,
        container_status=project.container_status,
        created_at=project.created_at, updated_at=project.updated_at,
        chat_session_count=chat_count,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await _get_user_project(db, user.id, project_id)

    # Remove sandbox container first
    try:
        cm = ContainerManager(db)
        await cm.remove_sandbox(project.id)
    except Exception as e:
        logger.error(f"Error removing sandbox for project {project.id}: {e}")

    # Get all chat session IDs for cascade delete
    result = await db.execute(
        select(ChatSession.id).where(ChatSession.project_id == project.id)
    )
    chat_ids = [row[0] for row in result.all()]

    if chat_ids:
        # Delete agent logs for all chat sessions
        await db.execute(
            delete(AgentLog).where(AgentLog.chat_session_id.in_(chat_ids))
        )
        # Delete messages for all chat sessions
        await db.execute(
            delete(Message).where(Message.chat_session_id.in_(chat_ids))
        )
        # Delete chat sessions
        await db.execute(
            delete(ChatSession).where(ChatSession.project_id == project.id)
        )

    # Delete workspace
    if os.path.exists(project.workspace_path):
        shutil.rmtree(project.workspace_path)

    await db.delete(project)
    await db.commit()


# --- Sandbox API endpoints (moved from sessions.py) ---

class ExecuteRequest(BaseModel):
    filename: str
    code: str


class ExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int


class PreviewResponse(BaseModel):
    preview_url: str
    status: str
    runtime_mode: str = "deploy"
    container_status: str = "running"


class DeployResponse(BaseModel):
    preview_url: str | None = None
    runtime_mode: str
    container_status: str


class SandboxStatusResponse(BaseModel):
    runtime_mode: str
    container_status: str
    container_id: str | None = None
    sandbox_node_id: str | None = None


@router.post("/{project_id}/execute", response_model=ExecuteResponse)
async def execute_code(
    project_id: str,
    body: ExecuteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    cm = ContainerManager(db)

    try:
        result = await cm.execute_code(project.id, body.filename, body.code)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {e}")

    return ExecuteResponse(**result)


@router.post("/{project_id}/preview", response_model=PreviewResponse)
async def start_preview(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    cm = ContainerManager(db)

    try:
        ip = await cm.start_deploy(project.id)
        await db.refresh(project)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    preview_url = f"/preview/{project.id}/"
    return PreviewResponse(
        preview_url=preview_url,
        status="running",
        runtime_mode=project.runtime_mode,
        container_status=project.container_status,
    )


@router.post("/{project_id}/deploy/start", response_model=DeployResponse)
async def start_deploy(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    cm = ContainerManager(db)

    try:
        await cm.start_deploy(project.id)
        await db.refresh(project)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deploy start failed: {e}")

    return DeployResponse(
        preview_url=f"/preview/{project.id}/",
        runtime_mode=project.runtime_mode,
        container_status=project.container_status,
    )


@router.post("/{project_id}/deploy/stop", response_model=DeployResponse)
async def stop_deploy(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    cm = ContainerManager(db)

    try:
        await cm.stop_deploy(project.id)
        await db.refresh(project)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deploy stop failed: {e}")

    return DeployResponse(
        runtime_mode=project.runtime_mode,
        container_status=project.container_status,
    )


@router.get("/{project_id}/sandbox", response_model=SandboxStatusResponse)
async def get_sandbox_status(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(db, user.id, project_id)
    cm = ContainerManager(db)
    actual_status = await cm.get_status(project.id)

    return SandboxStatusResponse(
        runtime_mode=project.runtime_mode,
        container_status=actual_status,
        container_id=project.container_id,
        sandbox_node_id=project.sandbox_node_id,
    )
