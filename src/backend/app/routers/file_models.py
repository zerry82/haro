from __future__ import annotations

from pydantic import BaseModel


class FileItem(BaseModel):
    name: str
    type: str
    size: int | None = None
    children_count: int | None = None


class FileListResponse(BaseModel):
    path: str
    items: list[FileItem]
    total: int | None = None
    has_more: bool = False
    limit: int | None = None
    offset: int = 0


class FileContentResponse(BaseModel):
    path: str
    content: str
    size: int
    language: str


class FileContentUpdate(BaseModel):
    content: str


class DirectoryCreateRequest(BaseModel):
    path: str


class FileMutationResponse(BaseModel):
    path: str
    type: str


class FileUploadResponse(BaseModel):
    path: str
    uploaded: list[str]


class FileSearchItem(BaseModel):
    path: str
    name: str
    item_type: str
    language: str | None = None
    extension: str | None = None
    room: str
    access_policy: str
    summary_status: str
    summary_snippet: str


class FileSearchResponse(BaseModel):
    query: str
    status: str = "ok"
    items: list[FileSearchItem]
