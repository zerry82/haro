"""리버스 프록시 — 샌드박스 웹서버로 프록시"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

import app.database as db_module
from app.models.project import Project
from app.services.container_manager import ContainerManager

router = APIRouter(tags=["preview"])


@router.get("/preview/{project_id}/{path:path}")
async def preview_proxy(project_id: str, path: str, request: Request):
    """GET /preview/{project_id}/{path} → 해당 컨테이너 IP:3000으로 프록시"""
    async with db_module.async_session_factory() as db:
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        if project.container_status != "running":
            raise HTTPException(status_code=503, detail="Sandbox is not running")

        cm = ContainerManager(db)
        ip = await cm.get_container_ip(project_id)
        if not ip:
            raise HTTPException(status_code=503, detail="Cannot determine container IP")

    # Proxy to container
    target_url = f"http://{ip}:3000/{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(target_url)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Preview server is not responding")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Proxy error: {e}")
