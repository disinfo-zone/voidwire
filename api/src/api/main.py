"""FastAPI application factory."""
from __future__ import annotations
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from voidwire.config import get_settings
from voidwire.database import close_engine
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.setup_guard import SetupGuardMiddleware
from api.routers import (
    public, health, setup_wizard,
    admin_readings, admin_sources, admin_templates, admin_dictionary,
    admin_settings, admin_pipeline, admin_events, admin_backup,
    admin_audit, admin_analytics, admin_llm, admin_threads, admin_signals,
    admin_keywords,
)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await close_engine()

def create_app() -> FastAPI:
    app = FastAPI(title="Voidwire API", version="0.1.0", lifespan=lifespan)
    settings = get_settings()
    allowed_origins = [settings.site_url, settings.admin_url]
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SetupGuardMiddleware)
    app.include_router(public.router, prefix="/v1", tags=["public"])
    app.include_router(health.router, tags=["health"])
    app.include_router(setup_wizard.router, prefix="/setup", tags=["setup"])
    app.include_router(admin_readings.router, prefix="/admin/readings", tags=["admin"])
    app.include_router(admin_sources.router, prefix="/admin/sources", tags=["admin"])
    app.include_router(admin_templates.router, prefix="/admin/templates", tags=["admin"])
    app.include_router(admin_dictionary.router, prefix="/admin/dictionary", tags=["admin"])
    app.include_router(admin_settings.router, prefix="/admin/settings", tags=["admin"])
    app.include_router(admin_pipeline.router, prefix="/admin/pipeline", tags=["admin"])
    app.include_router(admin_events.router, prefix="/admin/events", tags=["admin"])
    app.include_router(admin_backup.router, prefix="/admin/backup", tags=["admin"])
    app.include_router(admin_audit.router, prefix="/admin/audit", tags=["admin"])
    app.include_router(admin_analytics.router, prefix="/admin/analytics", tags=["admin"])
    app.include_router(admin_llm.router, prefix="/admin/llm", tags=["admin"])
    app.include_router(admin_threads.router, prefix="/admin/threads", tags=["admin"])
    app.include_router(admin_signals.router, prefix="/admin/signals", tags=["admin"])
    app.include_router(admin_keywords.router, prefix="/admin/keywords", tags=["admin"])
    return app

app = create_app()
