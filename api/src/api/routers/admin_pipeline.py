"""Admin pipeline management."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import AdminUser, AuditLog, PipelineRun, Reading, SiteSetting
from voidwire.schemas.pipeline import RegenerationMode

from api.dependencies import get_db, require_admin

router = APIRouter()
logger = logging.getLogger(__name__)

SCHEDULE_SETTING_KEY = "pipeline.schedule"
TIMEZONE_SETTING_KEY = "pipeline.timezone"
RUN_ON_START_SETTING_KEY = "pipeline.run_on_start"
AUTO_PUBLISH_SETTING_KEY = "pipeline.auto_publish"


class TriggerRequest(BaseModel):
    regeneration_mode: str | None = None
    date_context: str | None = None
    parent_run_id: str | None = None
    wait_for_completion: bool = True


class ScheduleUpdateRequest(BaseModel):
    pipeline_schedule: str
    timezone: str
    pipeline_run_on_start: bool = False
    auto_publish: bool | None = None


def _elapsed_seconds(started_at: datetime | None, ended_at: datetime | None) -> int | None:
    if started_at is None:
        return None
    end = ended_at or datetime.now(UTC)
    return max(int((end - started_at).total_seconds()), 0)


def _progress_hint(r: PipelineRun) -> str:
    if r.status == "completed":
        if r.error_detail:
            first_line = str(r.error_detail).strip().splitlines()[0]
            return f"Completed with fallback: {first_line[:180]}"
        return "Completed"
    if r.status == "failed":
        if r.error_detail:
            first_line = str(r.error_detail).strip().splitlines()[0]
            return f"Failed: {first_line[:180]}"
        return "Failed"

    elapsed = _elapsed_seconds(r.started_at, r.ended_at) or 0
    if elapsed > 900:
        return "Running longer than expected; synthesis may be stalled"

    if r.generated_output:
        return "Finalizing publish step"
    if r.interpretive_plan or r.prompt_payloads:
        return "Generating synthesis output"
    if r.thread_snapshot:
        return "Tracking continuity threads"
    if r.selected_signals:
        return "Selecting signals for narrative"
    if r.distilled_signals:
        return "Embedding and ranking signals"
    if r.ephemeris_json:
        return "Ingestion and distillation in progress"
    return "Starting ephemeris stage"


def _trigger_source(r: PipelineRun) -> str:
    artifacts = r.reused_artifacts if isinstance(r.reused_artifacts, dict) else {}
    source = str(artifacts.get("trigger_source", "scheduler")).strip().lower()
    return source or "scheduler"


def _run_summary(r: PipelineRun, reading: dict[str, Any] | None = None) -> dict:
    reading = reading or {}
    return {
        "id": str(r.id),
        "date_context": r.date_context.isoformat(),
        "run_number": r.run_number,
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "ended_at": r.ended_at.isoformat() if r.ended_at else None,
        "regeneration_mode": r.regeneration_mode,
        "error_detail": r.error_detail,
        "progress_hint": _progress_hint(r),
        "trigger_source": _trigger_source(r),
        "elapsed_seconds": _elapsed_seconds(r.started_at, r.ended_at),
        "reading_status": reading.get("status"),
        "reading_id": reading.get("id"),
        "reading_published_at": reading.get("published_at"),
    }


def _pipeline_lock_key(target_date: date) -> int:
    return int(hashlib.sha256(target_date.isoformat().encode()).hexdigest()[:15], 16) % (2**31)


async def _is_pipeline_lock_available(db: AsyncSession, target_date: date) -> bool:
    engine = db.bind
    if engine is None:
        return True
    if engine.dialect.name != "postgresql":
        return True
    lock_key = _pipeline_lock_key(target_date)
    async with engine.connect() as conn:
        tx = await conn.begin()
        try:
            result = await conn.execute(
                sa_text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": lock_key},
            )
            return bool(result.scalar())
        finally:
            if tx.is_active:
                try:
                    await tx.rollback()
                except Exception as exc:
                    logger.warning("Could not rollback lock probe transaction cleanly: %s", exc)


def _load_pipeline_runner():
    """Import lazily so admin API can still boot if pipeline package is missing."""
    try:
        from pipeline.orchestrator import run_pipeline
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Pipeline package is unavailable in API container. Rebuild API image.",
        ) from exc
    return run_pipeline


def _parse_daily_schedule(schedule: str) -> tuple[int, int]:
    parts = schedule.split()
    if len(parts) != 5:
        raise ValueError("Expected 5-part cron expression 'M H * * *'")
    minute_str, hour_str, dom, month, dow = parts
    if dom != "*" or month != "*" or dow != "*":
        raise ValueError("Only daily schedule format 'M H * * *' is supported")
    minute = int(minute_str)
    hour = int(hour_str)
    if minute < 0 or minute > 59 or hour < 0 or hour > 23:
        raise ValueError("Hour/minute out of range")
    return hour, minute


def _compute_next_run_iso(schedule: str, timezone_name: str) -> str | None:
    hour, minute = _parse_daily_schedule(schedule)
    tz = ZoneInfo(timezone_name)
    now = datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        from datetime import timedelta

        target = target + timedelta(days=1)
    return target.isoformat()


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _setting_value_dict(setting: SiteSetting | None) -> dict:
    if setting is None or not isinstance(setting.value, dict):
        return {}
    return setting.value


async def _load_scheduler_overrides(db: AsyncSession) -> tuple[str, str, bool]:
    settings = get_settings()
    schedule = settings.pipeline_schedule
    timezone_name = settings.timezone
    run_on_start = settings.pipeline_run_on_start

    result = await db.execute(
        select(SiteSetting).where(
            SiteSetting.key.in_(
                [SCHEDULE_SETTING_KEY, TIMEZONE_SETTING_KEY, RUN_ON_START_SETTING_KEY]
            )
        )
    )
    by_key = {row.key: row for row in result.scalars().all()}

    schedule_override = str(
        _setting_value_dict(by_key.get(SCHEDULE_SETTING_KEY)).get("cron", "")
    ).strip()
    if schedule_override:
        schedule = schedule_override

    timezone_override = str(
        _setting_value_dict(by_key.get(TIMEZONE_SETTING_KEY)).get("value", "")
    ).strip()
    if timezone_override:
        timezone_name = timezone_override

    if RUN_ON_START_SETTING_KEY in by_key:
        run_on_start = bool(
            _setting_value_dict(by_key.get(RUN_ON_START_SETTING_KEY)).get("enabled", run_on_start)
        )

    return schedule, timezone_name, run_on_start


async def _load_auto_publish_enabled(db: AsyncSession) -> bool:
    row = await db.get(SiteSetting, AUTO_PUBLISH_SETTING_KEY)
    if not row:
        return False
    value = _setting_value_dict(row)
    return bool(value.get("enabled", False))


async def _reading_summary_by_run_id(
    db: AsyncSession, run_ids: list[UUID]
) -> dict[UUID, dict[str, Any]]:
    if not run_ids:
        return {}
    result = await db.execute(select(Reading).where(Reading.run_id.in_(run_ids)))
    return {
        r.run_id: {
            "id": str(r.id),
            "status": r.status,
            "published_at": r.published_at.isoformat() if r.published_at else None,
        }
        for r in result.scalars().all()
    }


async def _upsert_setting(
    db: AsyncSession, key: str, value: dict, category: str = "pipeline"
) -> None:
    setting = await db.get(SiteSetting, key)
    if setting:
        setting.value = value
        setting.category = category
    else:
        db.add(SiteSetting(key=key, value=value, category=category))


async def _run_pipeline_background(
    run_pipeline,
    *,
    date_context: date | None,
    regeneration_mode: RegenerationMode | None,
    parent_run_id: UUID | None,
    trigger_source: str,
) -> None:
    try:
        run_id = await run_pipeline(
            date_context=date_context,
            regeneration_mode=regeneration_mode,
            parent_run_id=parent_run_id,
            trigger_source=trigger_source,
        )
        logger.info("Background pipeline run completed successfully: %s", run_id)
    except RuntimeError as exc:
        if "advisory lock" in str(exc).lower():
            logger.warning("Background pipeline run skipped due to lock conflict: %s", exc)
            return
        logger.exception("Background pipeline run failed: %s", exc)
    except Exception as exc:
        logger.exception("Background pipeline run failed: %s", exc)


@router.get("/runs")
async def list_runs(
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    result = await db.execute(
        select(PipelineRun)
        .order_by(PipelineRun.started_at.desc())
        .offset((page - 1) * 20)
        .limit(20)
    )
    runs = result.scalars().all()
    reading_map = await _reading_summary_by_run_id(db, [r.id for r in runs])
    return [_run_summary(r, reading_map.get(r.id)) for r in runs]


@router.get("/runs/{run_id}")
async def get_run(
    run_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)
):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    reading_map = await _reading_summary_by_run_id(db, [run_id])
    reading = reading_map.get(run_id, {})
    return {
        **_run_summary(run, reading),
        "seed": run.seed,
        "code_version": run.code_version,
        "model_config_json": run.model_config_json,
        "template_versions": run.template_versions,
        "selected_signals": run.selected_signals,
        "thread_snapshot": run.thread_snapshot,
        "interpretive_plan": run.interpretive_plan,
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
    }


@router.get("/schedule")
async def get_schedule(
    db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)
):
    settings = get_settings()
    (
        effective_schedule,
        effective_timezone,
        effective_run_on_start,
    ) = await _load_scheduler_overrides(db)
    auto_publish_enabled = await _load_auto_publish_enabled(db)
    next_run = None
    parse_error = None
    try:
        next_run = _compute_next_run_iso(effective_schedule, effective_timezone)
    except Exception as exc:
        parse_error = str(exc)
    return {
        "pipeline_schedule": effective_schedule,
        "timezone": effective_timezone,
        "pipeline_run_on_start": effective_run_on_start,
        "auto_publish": auto_publish_enabled,
        "source": "database_override"
        if (
            effective_schedule != settings.pipeline_schedule
            or effective_timezone != settings.timezone
            or effective_run_on_start != settings.pipeline_run_on_start
        )
        else "environment",
        "env_defaults": {
            "pipeline_schedule": settings.pipeline_schedule,
            "timezone": settings.timezone,
            "pipeline_run_on_start": settings.pipeline_run_on_start,
        },
        "next_run_at": next_run,
        "parse_error": parse_error,
        "edit_location": "UI (stored in DB) or .env (PIPELINE_SCHEDULE, TIMEZONE, PIPELINE_RUN_ON_START)",
    }


@router.put("/schedule")
async def update_schedule(
    req: ScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    # Validate config before persisting
    _parse_daily_schedule(req.pipeline_schedule.strip())
    try:
        ZoneInfo(req.timezone.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {req.timezone}") from exc

    await _upsert_setting(
        db,
        SCHEDULE_SETTING_KEY,
        {"cron": req.pipeline_schedule.strip()},
    )
    await _upsert_setting(
        db,
        TIMEZONE_SETTING_KEY,
        {"value": req.timezone.strip()},
    )
    await _upsert_setting(
        db,
        RUN_ON_START_SETTING_KEY,
        {"enabled": bool(req.pipeline_run_on_start)},
    )
    if req.auto_publish is not None:
        await _upsert_setting(
            db,
            AUTO_PUBLISH_SETTING_KEY,
            {"enabled": bool(req.auto_publish)},
        )

    db.add(
        AuditLog(
            user_id=user.id,
            action="pipeline.schedule.update",
            target_type="pipeline",
            target_id="scheduler",
            detail={
                "pipeline_schedule": req.pipeline_schedule.strip(),
                "timezone": req.timezone.strip(),
                "pipeline_run_on_start": bool(req.pipeline_run_on_start),
                "auto_publish": req.auto_publish,
            },
        )
    )

    return {"status": "ok"}


@router.get("/runs/{run_id}/artifacts")
async def get_run_artifacts(
    run_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)
):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "ephemeris_json": run.ephemeris_json,
        "distilled_signals": run.distilled_signals,
        "selected_signals": run.selected_signals,
        "thread_snapshot": run.thread_snapshot,
        "prompt_payloads": run.prompt_payloads,
        "interpretive_plan": run.interpretive_plan,
        "generated_output": run.generated_output,
        "model_config_json": run.model_config_json,
        "ephemeris_hash": run.ephemeris_hash,
        "distillation_hash": run.distillation_hash,
        "selection_hash": run.selection_hash,
    }


@router.post("/weather/regenerate")
async def regenerate_weather_descriptions(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    from api.services.weather_service import regenerate_weather

    result = await regenerate_weather(db)
    if not result:
        raise HTTPException(status_code=404, detail="No pipeline run or LLM unavailable")
    return {"detail": "Weather descriptions regenerated", "weather": result}


@router.post("/trigger")
async def trigger_pipeline(
    request: Request,
    req: TriggerRequest = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    run_pipeline = _load_pipeline_runner()
    if req is None:
        req = TriggerRequest()
    dc = None
    if req.date_context:
        dc = date.fromisoformat(req.date_context)
    mode = None
    if req.regeneration_mode:
        mode = RegenerationMode(req.regeneration_mode)
    parent = UUID(req.parent_run_id) if req.parent_run_id else None

    if dc is not None:
        target_date = dc
    else:
        target_date = datetime.now(ZoneInfo(get_settings().timezone)).date()
    running = await db.execute(
        select(PipelineRun).where(
            PipelineRun.date_context == target_date,
            PipelineRun.status == "running",
        )
    )
    if running.scalars().first() is not None:
        raise HTTPException(
            status_code=409, detail="A pipeline run for this date is already in progress."
        )
    if not await _is_pipeline_lock_available(db, target_date):
        raise HTTPException(
            status_code=409, detail="A pipeline run for this date is already in progress."
        )

    db.add(
        AuditLog(
            user_id=user.id,
            action="pipeline.trigger",
            target_type="pipeline",
            target_id=target_date.isoformat(),
            detail={
                "regeneration_mode": req.regeneration_mode,
                "date_context": target_date.isoformat(),
                "parent_run_id": req.parent_run_id,
                "trigger_source": "manual",
                "wait_for_completion": bool(req.wait_for_completion),
            },
            ip_address=_client_ip(request),
        )
    )

    if not req.wait_for_completion:
        asyncio.create_task(
            _run_pipeline_background(
                run_pipeline,
                date_context=dc,
                regeneration_mode=mode,
                parent_run_id=parent,
                trigger_source="manual",
            )
        )
        return {
            "status": "started",
            "mode": "background",
            "date_context": target_date.isoformat(),
        }

    try:
        run_id = await run_pipeline(
            date_context=dc,
            regeneration_mode=mode,
            parent_run_id=parent,
            trigger_source="manual",
        )
    except RuntimeError as exc:
        if "advisory lock" in str(exc).lower():
            raise HTTPException(
                status_code=409, detail="A pipeline run for this date is already in progress."
            ) from exc
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {exc}") from exc
    return {"status": "triggered", "run_id": str(run_id)}
