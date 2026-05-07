from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.project import Project
from app.models.user import User
from app.routers.file_models import (
    DirectoryCreateRequest,
    FileContentResponse,
    FileContentUpdate,
    FileItem,
    FileListResponse,
    FileMutationResponse,
    FileSearchItem,
    FileSearchResponse,
    FileUploadResponse,
)
from app.services.file_conversion import (
    EDITABLE_EXTENSIONS,
    excel_to_csv_outputs,
    get_language,
    is_excel_file,
)
from app.services.file_path_policy import (
    assert_read_allowed,
    assert_write_allowed,
    join_workspace_path,
    validate_file_name,
    validate_workspace_path,
)
from app.services.harness import ensure_harness_structure
from app.services.workspace_file_db import (
    WorkspaceSearchUnavailable,
    atomic_write_bytes,
    atomic_write_text,
    list_workspace_directory_page,
    mark_workspace_summary_stale,
    search_workspace_files,
    sync_workspace_path,
)
from app.services.workspace_index import rebuild_workspace_index, update_file_summary

router = APIRouter(prefix="/api/projects/{project_id}/files", tags=["files"])


async def _get_workspace(db: AsyncSession, user_id: str, project_id: str) -> str:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.workspace_path


@router.get("", response_model=FileListResponse)
async def list_files(
    project_id: str,
    path: str = Query("/"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await _get_workspace(db, user.id, project_id)
    ensure_harness_structure(workspace, user.id, initialize_git=path == "/")
    assert_read_allowed(path)
    full_path = validate_workspace_path(workspace, path)
    if not os.path.isdir(full_path):
        raise HTTPException(status_code=404, detail="Directory not found")

    page = list_workspace_directory_page(workspace, path, limit=limit, offset=offset)
    items = [FileItem(**item) for item in page["items"]]
    return FileListResponse(
        path=path,
        items=items,
        total=page["total"],
        has_more=page["has_more"],
        limit=page["limit"],
        offset=page["offset"],
    )


@router.get("/search", response_model=FileSearchResponse)
async def search_files(
    project_id: str,
    q: str = Query(""),
    room: str | None = Query(None),
    item_type: str | None = Query(None),
    language: str | None = Query(None),
    extension: str | None = Query(None),
    access_policy: str | None = Query(None),
    chat_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await _get_workspace(db, user.id, project_id)
    ensure_harness_structure(workspace, user.id, initialize_git=False)
    db_item_type = "dir" if item_type == "directory" else "file" if item_type == "file" else item_type
    try:
        items = search_workspace_files(
            workspace,
            q,
            room=room,
            item_type=db_item_type,
            language=language,
            extension=extension,
            access_policy=access_policy,
            chat_id=chat_id,
            limit=limit,
        )
    except WorkspaceSearchUnavailable:
        return FileSearchResponse(query=q, status="search_unavailable", items=[])
    return FileSearchResponse(query=q, items=[FileSearchItem(**item) for item in items])


@router.post("/directories", response_model=FileMutationResponse, status_code=201)
async def create_directory(
    project_id: str,
    body: DirectoryCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await _get_workspace(db, user.id, project_id)
    ensure_harness_structure(workspace, user.id, initialize_git=False)
    assert_write_allowed(body.path)
    full_path = validate_workspace_path(workspace, body.path)
    if os.path.exists(full_path):
        raise HTTPException(status_code=409, detail="Path already exists")

    parent = os.path.dirname(full_path)
    if not os.path.isdir(parent):
        raise HTTPException(status_code=404, detail="Parent directory not found")

    os.mkdir(full_path)
    sync_workspace_path(workspace, body.path, source_kind="user")
    await rebuild_workspace_index(workspace)
    return FileMutationResponse(path=body.path, type="directory")


@router.post("/upload", response_model=FileUploadResponse)
async def upload_files(
    project_id: str,
    path: str = Query("/"),
    overwrite: bool = Query(False),
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await _get_workspace(db, user.id, project_id)
    ensure_harness_structure(workspace, user.id, initialize_git=False)
    assert_write_allowed(path)
    target_dir = validate_workspace_path(workspace, path)
    if not os.path.isdir(target_dir):
        raise HTTPException(status_code=404, detail="Directory not found")

    seen: set[str] = set()
    upload_items: list[tuple[str, bytes]] = []
    for upload in files:
        filename = upload.filename or ""
        validate_file_name(filename)
        if filename in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate upload name: {filename}")
        seen.add(filename)
        content = await upload.read()
        if is_excel_file(filename):
            for relative_name, csv_content in excel_to_csv_outputs(filename, content):
                upload_items.append((relative_name, csv_content))
        else:
            upload_items.append((filename, content))

    generated_paths: set[str] = set()
    existed_before: dict[str, bool] = {}
    for relative_name, _content in upload_items:
        relative_path = join_workspace_path(path, relative_name)
        target_path = validate_workspace_path(workspace, relative_path)
        if target_path in generated_paths:
            raise HTTPException(status_code=400, detail=f"Duplicate upload output: {relative_name}")
        generated_paths.add(target_path)

        parent = os.path.dirname(target_path)
        if os.path.exists(parent) and not os.path.isdir(parent):
            raise HTTPException(status_code=409, detail=f"File already exists: {os.path.basename(parent)}")
        if os.path.isdir(target_path):
            raise HTTPException(status_code=409, detail=f"Directory already exists: {relative_name}")
        existed_before[relative_path] = os.path.exists(target_path)
        if os.path.exists(target_path) and not overwrite:
            raise HTTPException(status_code=409, detail=f"File already exists: {relative_name}")

    uploaded: list[str] = []
    for relative_name, content in upload_items:
        relative_path = join_workspace_path(path, relative_name)
        target_path = validate_workspace_path(workspace, relative_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        atomic_write_bytes(target_path, content)
        uploaded.append(relative_path)
        await update_file_summary(workspace, relative_path, "modified" if existed_before.get(relative_path) else "created")

    return FileUploadResponse(path=path, uploaded=uploaded)


@router.get("/content", response_model=FileContentResponse)
async def get_file_content(
    project_id: str,
    path: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await _get_workspace(db, user.id, project_id)
    ensure_harness_structure(workspace, user.id, initialize_git=False)
    assert_read_allowed(path)
    full_path = validate_workspace_path(workspace, path)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    language = get_language(path)
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
    ensure_harness_structure(workspace, user.id, initialize_git=False)
    assert_write_allowed(path)
    full_path = validate_workspace_path(workspace, path)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    ext = os.path.splitext(path)[1].lower()
    if ext not in EDITABLE_EXTENSIONS:
        raise HTTPException(status_code=415, detail="File type is not editable")

    atomic_write_text(full_path, body.content)
    mark_workspace_summary_stale(workspace, path)

    await update_file_summary(workspace, path, "modified")

    language = get_language(path)
    content = body.content
    return FileContentResponse(path=path, content=content, size=len(content), language=language)
