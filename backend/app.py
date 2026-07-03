"""
FastAPI application factory.

Creates the app, registers routes, mounts static files, and initialises the DB.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import init_db


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""

    app = FastAPI(
        title="AutoScan Pro",
        description="Car Inspection Desktop Application API",
        version="1.0.0",
    )

    # CORS — allow the PyWebView window (and dev tools) to call the API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Startup ──────────────────────────────────────────────────────
    @app.on_event("startup")
    def on_startup():
        init_db()

    # ── Register API routes ──────────────────────────────────────────
    from backend.routes.auth_routes import router as auth_router
    from backend.routes.vehicle_routes import router as vehicle_router
    from backend.routes.inspection_routes import router as inspection_router
    from backend.routes.defect_routes import router as defect_router
    from backend.routes.report_routes import router as report_router
    from backend.routes.ws_routes import router as ws_router

    app.include_router(auth_router)
    app.include_router(vehicle_router)
    app.include_router(inspection_router)
    app.include_router(defect_router)
    app.include_router(report_router)
    app.include_router(ws_router)

    # ── Serve uploaded files (defect snapshots) ──────────────────────
    uploads_dir = settings.UPLOADS_DIR.parent  # "uploads/"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    # ── Serve frontend static files ──────────────────────────────────
    frontend_dir = settings.FRONTEND_DIR
    if frontend_dir.exists():
        # Mount static assets (css, js, assets)
        for sub in ("css", "js", "assets"):
            sub_dir = frontend_dir / sub
            if sub_dir.exists():
                app.mount(f"/{sub}", StaticFiles(directory=str(sub_dir)), name=sub)

        # SPA fallback: serve index.html for all non-API routes
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # If the path looks like a file with an extension, try to serve it
            requested = frontend_dir / full_path
            if requested.is_file():
                return FileResponse(str(requested))
            # Otherwise, serve index.html (SPA routing)
            index = frontend_dir / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return {"detail": "Frontend not found"}
    else:
        @app.get("/")
        def root():
            return {
                "message": "AutoScan Pro API is running",
                "docs": "/docs",
                "note": "Frontend directory not found. Place frontend files in frontend/",
            }

    return app
