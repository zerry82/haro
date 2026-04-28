from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.project import Project
from app.models.user import User
from app.services.workspace_index import update_file_summary

router = APIRouter(prefix="/api/projects/{project_id}/files", tags=["files"])


class FileItem(BaseModel):
    name: str
    type: str
    size: int | None = None
    children_count: int | None = None


class FileListResponse(BaseModel):
    path: str
    items: list[FileItem]


class FileContentResponse(BaseModel):
    path: str
    content: str
    size: int
    language: str


class FileContentUpdate(BaseModel):
    content: str


LANG_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".html": "html", ".css": "css", ".json": "json",
    ".csv": "csv",
    ".md": "markdown", ".yaml": "yaml", ".yml": "yaml",
    ".txt": "plaintext", ".svg": "xml",
}

EDITABLE_EXTENSIONS = {
    ".html", ".md", ".csv", ".ts", ".js", ".json",
    ".txt", ".css", ".py", ".yaml", ".yml", ".svg",
}


async def _get_workspace(db: AsyncSession, user_id: str, project_id: str) -> str:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.workspace_path


def _validate_path(workspace: str, requested: str) -> str:
    full = os.path.realpath(os.path.join(workspace, requested.lstrip("/")))
    if not full.startswith(os.path.realpath(workspace)):
        raise HTTPException(status_code=403, detail="Path traversal denied")
    return full


def _get_language(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return LANG_MAP.get(ext, "plaintext")


@router.get("", response_model=FileListResponse)
async def list_files(
    project_id: str,
    path: str = Query("/"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await _get_workspace(db, user.id, project_id)
    full_path = _validate_path(workspace, path)
    if not os.path.isdir(full_path):
        raise HTTPException(status_code=404, detail="Directory not found")

    items: list[FileItem] = []
    for entry in os.scandir(full_path):
        if entry.name.startswith(".openclaw"):
            continue
        if entry.is_dir():
            children = len([e for e in os.scandir(entry.path) if not e.name.startswith(".openclaw")])
            items.append(FileItem(name=entry.name, type="directory", children_count=children))
        else:
            items.append(FileItem(name=entry.name, type="file", size=entry.stat().st_size))
    items.sort(key=lambda x: (x.type == "file", x.name))
    return FileListResponse(path=path, items=items)


@router.get("/content", response_model=FileContentResponse)
async def get_file_content(
    project_id: str,
    path: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await _get_workspace(db, user.id, project_id)
    full_path = _validate_path(workspace, path)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    language = _get_language(path)
    return FileContentResponse(path=path, content=content, size=len(content), language=language)


@router.put("/content", response_model=FileContentResponse)
async def update_file_content(
    project_id: str,
    body: FileContentUpdate,
    path: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await _get_workspace(db, user.id, project_id)
    full_path = _validate_path(workspace, path)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    ext = os.path.splitext(path)[1].lower()
    if ext not in EDITABLE_EXTENSIONS:
        raise HTTPException(status_code=415, detail="File type is not editable")

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(body.content)

    await update_file_summary(workspace, path, "modified")

    language = _get_language(path)
    content = body.content
    return FileContentResponse(path=path, content=content, size=len(content), language=language)
