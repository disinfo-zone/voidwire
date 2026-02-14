"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from voidwire.config import get_settings
from voidwire.database import close_engine, get_engine
from voidwire.models import Base

from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.setup_guard import SetupGuardMiddleware
from api.routers import (
    admin_analytics,
    admin_audit,
    admin_auth,
    admin_backup,
    admin_dictionary,
    admin_events,
    admin_keywords,
    admin_llm,
    admin_pipeline,
    admin_readings,
    admin_settings,
    admin_signals,
    admin_sources,
    admin_templates,
    admin_threads,
    health,
    public,
    setup_wizard,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        engine = get_engine()
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            await connection.run_sync(Base.metadata.create_all)
        yield
    finally:
        redis_client = getattr(app.state, "_rate_limit_redis", None)
        if redis_client is not None:
            await redis_client.aclose()
        await close_engine()


def _warn_insecure_defaults() -> None:
    settings = get_settings()
    if settings.secret_key == "change-me-in-production":
        logger.warning("SECRET_KEY uses insecure default value")
    if not settings.encryption_key:
        logger.warning("ENCRYPTION_KEY is empty; encrypted secrets will fail")


def create_app() -> FastAPI:
    app = FastAPI(title="Voidwire API", version="0.1.0", lifespan=lifespan)
    settings = get_settings()
    _warn_insecure_defaults()
    allowed_origins = [settings.site_url, settings.admin_url]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SetupGuardMiddleware)
    app.include_router(admin_auth.router, prefix="/admin/auth", tags=["admin"])
    app.include_router(admin_readings.router, prefix="/admin/readings", tags=["admin"])
    app.include_router(admin_keywords.router, prefix="/admin/keywords", tags=["admin"])
    app.include_router(admin_llm.router, prefix="/admin/llm", tags=["admin"])
    app.include_router(admin_settings.router, prefix="/admin/settings", tags=["admin"])
    app.include_router(admin_sources.router, prefix="/admin/sources", tags=["admin"])
    app.include_router(admin_templates.router, prefix="/admin/templates", tags=["admin"])
    app.include_router(admin_dictionary.router, prefix="/admin/dictionary", tags=["admin"])
    app.include_router(admin_pipeline.router, prefix="/admin/pipeline", tags=["admin"])
    app.include_router(admin_events.router, prefix="/admin/events", tags=["admin"])
    app.include_router(admin_backup.router, prefix="/admin/backup", tags=["admin"])
    app.include_router(admin_audit.router, prefix="/admin/audit", tags=["admin"])
    app.include_router(admin_analytics.router, prefix="/admin/analytics", tags=["admin"])
    app.include_router(admin_threads.router, prefix="/admin/threads", tags=["admin"])
    app.include_router(admin_signals.router, prefix="/admin/signals", tags=["admin"])
    app.include_router(health.router, tags=["health"])
    app.include_router(setup_wizard.router, prefix="/setup", tags=["setup"])
    app.include_router(public.router, prefix="/v1", tags=["public"])
    return app


app = create_app()
