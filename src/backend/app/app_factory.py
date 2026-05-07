from __future__ import annotations

import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, chats, files, logs, messages, preview, projects, sessions, skills
from app.startup.lifespan import lifespan


def create_app() -> FastAPI:
    app = FastAPI(title="haro", version="0.1.0", lifespan=lifespan)
    _register_middleware(app)
    _register_routes(app)
    _mount_frontend_dist(app)
    return app


def _register_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _register_routes(app: FastAPI) -> None:
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(chats.router)
    app.include_router(sessions.router)
    app.include_router(messages.router)
    app.include_router(files.router)
    app.include_router(skills.router)
    app.include_router(logs.router)
    app.include_router(preview.router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}


def _mount_frontend_dist(app: FastAPI) -> None:
    frontend_dist = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if not frontend_dist.is_dir():
        return

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = frontend_dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_dist / "index.html"))
