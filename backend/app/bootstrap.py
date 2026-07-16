from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routers import (
    assistants_router,
    plan_control_router,
    project_girder_router,
    project_master_router,
    scheduling_router,
    system_router,
)
from .config.environment import load_local_config
from .project_master.service import default_project_master_service


NETLIFY_FRONTEND_ORIGIN = "https://project-scheduling-lili-big.netlify.app"
DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8888",
    NETLIFY_FRONTEND_ORIGIN,
]
DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def csv_env(name: str, defaults: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    values = [value.strip().rstrip("/") for value in raw.split(",") if value.strip()]
    return values or defaults


def create_app() -> FastAPI:
    load_local_config()
    app = FastAPI(title="Bridge Lower-Structure CP-SAT Scheduler", version="0.1.0")
    app.state.project_master_service = default_project_master_service()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=csv_env("SCHEDULER_CORS_ORIGINS", DEFAULT_CORS_ORIGINS),
        allow_origin_regex=os.getenv(
            "SCHEDULER_CORS_ORIGIN_REGEX",
            r"https://[a-z0-9-]+--project-scheduling-lili-big\.netlify\.app",
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system_router)
    app.include_router(scheduling_router)
    app.include_router(assistants_router)
    app.include_router(project_girder_router)
    app.include_router(project_master_router)
    app.include_router(plan_control_router)

    if DIST_DIR.exists():
        app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def serve_frontend(full_path: str):
            requested = DIST_DIR / full_path
            if full_path and requested.is_file():
                return FileResponse(requested)
            return FileResponse(DIST_DIR / "index.html")

    return app
