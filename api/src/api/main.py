"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from voidwire.config import get_settings
from voidwire.database import close_engine, get_engine

from api.middleware.csrf import CSRFMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.setup_guard import SetupGuardMiddleware
from api.routers import (
    admin_accounts,
    admin_analytics,
    admin_audit,
    admin_auth,
    admin_backup,
    admin_content,
    admin_dictionary,
    admin_events,
    admin_keywords,
    admin_llm,
    admin_pipeline,
    admin_readings,
    admin_settings,
    admin_signals,
    admin_site,
    admin_sources,
    admin_templates,
    admin_threads,
    health,
    public,
    setup_wizard,
    stripe_webhook,
    user_auth,
    user_profile,
    user_readings,
    user_subscription,
)
from api.services.async_job_service import run_async_job_worker
from api.services.maintenance import run_maintenance_worker

logger = logging.getLogger(__name__)


async def _assert_database_revision_current() -> None:
    settings = get_settings()
    if settings.skip_migration_check:
        return

    repo_root = Path(__file__).resolve().parents[3]
    alembic_ini = repo_root / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("alembic.ini not found; skipping migration revision check")
        return

    alembic_cfg = AlembicConfig(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(repo_root / "alembic"))
    script = ScriptDirectory.from_config(alembic_cfg)
    expected_heads = set(script.get_heads())
    if not expected_heads:
        return

    engine = get_engine()
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT version_num FROM alembic_version"))
            current_revisions = {str(row[0]) for row in result.fetchall() if row and row[0]}
    except Exception as exc:
        raise RuntimeError(
            "Database migration revision check failed. "
            "Run `alembic upgrade head` before starting the API."
        ) from exc

    if current_revisions != expected_heads:
        raise RuntimeError(
            "Database schema revision mismatch: "
            f"db={sorted(current_revisions)} expected={sorted(expected_heads)}. "
            "Run `alembic upgrade head`."
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    job_stop_event: asyncio.Event | None = None
    job_worker_task: asyncio.Task | None = None
    maintenance_stop_event: asyncio.Event | None = None
    maintenance_task: asyncio.Task | None = None
    try:
        engine = get_engine()
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await _assert_database_revision_current()
        job_stop_event = asyncio.Event()
        job_worker_task = asyncio.create_task(run_async_job_worker(job_stop_event))
        maintenance_stop_event = asyncio.Event()
        maintenance_task = asyncio.create_task(run_maintenance_worker(maintenance_stop_event))
        yield
    finally:
        if job_stop_event is not None:
            job_stop_event.set()
        if job_worker_task is not None:
            try:
                await asyncio.wait_for(job_worker_task, timeout=5)
            except Exception:
                job_worker_task.cancel()
                with suppress(Exception):
                    await job_worker_task
        if maintenance_stop_event is not None:
            maintenance_stop_event.set()
        if maintenance_task is not None:
            try:
                await asyncio.wait_for(maintenance_task, timeout=5)
            except Exception:
                maintenance_task.cancel()
                with suppress(Exception):
                    await maintenance_task
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
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SetupGuardMiddleware)
    app.include_router(admin_auth.router, prefix="/admin/auth", tags=["admin"])
    app.include_router(admin_accounts.router, prefix="/admin/accounts", tags=["admin"])
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
    app.include_router(admin_content.router, prefix="/admin/content", tags=["admin"])
    app.include_router(admin_audit.router, prefix="/admin/audit", tags=["admin"])
    app.include_router(admin_analytics.router, prefix="/admin/analytics", tags=["admin"])
    app.include_router(admin_threads.router, prefix="/admin/threads", tags=["admin"])
    app.include_router(admin_signals.router, prefix="/admin/signals", tags=["admin"])
    app.include_router(admin_site.router, prefix="/admin/site", tags=["admin"])
    app.include_router(health.router, tags=["health"])
    app.include_router(setup_wizard.router, prefix="/setup", tags=["setup"])
    app.include_router(public.router, prefix="/v1", tags=["public"])
    app.include_router(user_auth.router, prefix="/v1/user/auth", tags=["user-auth"])
    app.include_router(user_profile.router, prefix="/v1/user/profile", tags=["user-profile"])
    app.include_router(user_readings.router, prefix="/v1/user/readings", tags=["user-readings"])
    app.include_router(
        user_subscription.router,
        prefix="/v1/user/subscription",
        tags=["user-subscription"],
    )
    app.include_router(stripe_webhook.router, prefix="/v1/stripe", tags=["stripe"])
    return app


app = create_app()
