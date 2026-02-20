"""User personal reading endpoints."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AsyncJob, PersonalReading, User

from api.dependencies import get_current_public_user, get_db
from api.services.async_job_service import (
    ASYNC_JOB_TYPE_PERSONAL_READING,
    enqueue_personal_reading_job,
    serialize_async_job,
)
from api.services.personal_reading_service import PersonalReadingService
from api.services.subscription_service import get_user_tier

router = APIRouter()


class PersonalReadingJobRequest(BaseModel):
    tier: str = "auto"  # auto|free|pro
    force_refresh: bool = False


async def _can_force_refresh_reading(user: User, db: AsyncSession) -> bool:
    return bool(getattr(user, "is_test_user", False)) or bool(
        getattr(user, "is_admin_user", False)
    )


def _resolve_requested_tier(*, requested_tier: str, subscription_tier: str) -> str:
    normalized_request = str(requested_tier or "auto").strip().lower() or "auto"
    if normalized_request not in {"auto", "free", "pro"}:
        raise HTTPException(status_code=400, detail="tier must be one of: auto, free, pro")

    effective_subscription_tier = "pro" if str(subscription_tier).strip().lower() == "pro" else "free"
    if normalized_request == "auto":
        return effective_subscription_tier
    if normalized_request == "pro" and effective_subscription_tier != "pro":
        raise HTTPException(status_code=403, detail="Pro reading access requires a pro subscription")
    return normalized_request


def _coverage_window(reading: PersonalReading) -> tuple[date, date]:
    if reading.tier == "free":
        start = reading.date_context - timedelta(days=reading.date_context.weekday())
        end = start + timedelta(days=6)
        return start, end
    return reading.date_context, reading.date_context


def _coverage_label(reading: PersonalReading, start: date, end: date) -> str:
    if reading.tier == "free":
        return f"Week of {start.isoformat()} to {end.isoformat()}"
    return f"Daily reading for {start.isoformat()}"


def _reading_payload(
    reading: PersonalReading,
    *,
    include_template_version: bool = False,
) -> dict:
    content = reading.content or {}
    metadata_raw = getattr(reading, "generation_metadata", None)
    metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
    coverage_start, coverage_end = _coverage_window(reading)
    payload = {
        "id": str(reading.id) if reading.id else None,
        "tier": reading.tier,
        "date_context": reading.date_context.isoformat(),
        "coverage_start": coverage_start.isoformat(),
        "coverage_end": coverage_end.isoformat(),
        "coverage_label": _coverage_label(reading, coverage_start, coverage_end),
        "title": content.get("title", ""),
        "body": content.get("body", ""),
        "sections": content.get("sections", []),
        "word_count": content.get("word_count", 0),
        "transit_highlights": content.get("transit_highlights", []),
        "house_system_used": reading.house_system_used,
        "created_at": reading.created_at.isoformat() if reading.created_at else None,
    }
    if include_template_version:
        payload["template_version"] = metadata.get("template_version")
    return payload


@router.get("/personal")
async def get_current_personal_reading(
    tier: str = Query(default="auto"),
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current personal reading for requested tier (auto/free/pro)."""
    if not user.profile:
        raise HTTPException(
            status_code=400,
            detail="Complete your birth data profile first",
        )

    subscription_tier = await get_user_tier(user, db)
    effective_tier = _resolve_requested_tier(
        requested_tier=tier,
        subscription_tier=subscription_tier,
    )

    if effective_tier == "pro":
        reading = await PersonalReadingService.get_or_generate_pro_reading(user, db)
    else:
        reading = await PersonalReadingService.get_or_generate_free_reading(user, db)

    if not reading:
        raise HTTPException(
            status_code=503,
            detail="Unable to generate reading. Personal reading LLM slot may not be configured.",
        )

    include_template_version = await _can_force_refresh_reading(user, db)
    return _reading_payload(reading, include_template_version=include_template_version)


@router.get("/personal/current")
async def get_current_personal_reading_without_generation(
    tier: str = Query(default="auto"),
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(
            status_code=400,
            detail="Complete your birth data profile first",
        )

    subscription_tier = await get_user_tier(user, db)
    effective_tier = _resolve_requested_tier(
        requested_tier=tier,
        subscription_tier=subscription_tier,
    )
    include_template_version = await _can_force_refresh_reading(user, db)
    today = date.today()
    target_week = today.isocalendar()
    result = await db.execute(
        select(PersonalReading)
        .where(
            PersonalReading.user_id == user.id,
            PersonalReading.tier == effective_tier,
        )
        .order_by(PersonalReading.created_at.desc())
        .limit(20)
    )
    candidates = result.scalars().all()
    for reading in candidates:
        if effective_tier == "free":
            iso = reading.date_context.isocalendar()
            if (iso[0], iso[1]) == (target_week[0], target_week[1]):
                return _reading_payload(
                    reading,
                    include_template_version=include_template_version,
                )
        elif reading.date_context == today:
            return _reading_payload(
                reading,
                include_template_version=include_template_version,
            )

    raise HTTPException(status_code=404, detail="No current reading yet")


@router.post("/personal/jobs")
async def enqueue_personal_reading_generation(
    req: PersonalReadingJobRequest,
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(
            status_code=400,
            detail="Complete your birth data profile first",
        )

    requested_tier = str(req.tier or "auto").strip().lower() or "auto"
    force_refresh = bool(req.force_refresh)
    if force_refresh and not await _can_force_refresh_reading(user, db):
        raise HTTPException(
            status_code=403,
            detail="Force refresh is only available for admin/test users",
        )

    subscription_tier = await get_user_tier(user, db)
    tier = _resolve_requested_tier(
        requested_tier=requested_tier,
        subscription_tier=subscription_tier,
    )

    job = await enqueue_personal_reading_job(
        db,
        user_id=user.id,
        tier=tier,
        target_date=date.today(),
        force_refresh=force_refresh,
    )
    return serialize_async_job(job)


@router.get("/personal/jobs")
async def list_personal_reading_jobs(
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AsyncJob)
        .where(
            AsyncJob.user_id == user.id,
            AsyncJob.job_type == ASYNC_JOB_TYPE_PERSONAL_READING,
        )
        .order_by(AsyncJob.created_at.desc())
        .limit(limit)
    )
    return [serialize_async_job(job) for job in result.scalars().all()]


@router.get("/personal/jobs/{job_id}")
async def get_personal_reading_job(
    job_id: str,
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(
        select(AsyncJob).where(
            AsyncJob.id == job_uuid,
            AsyncJob.user_id == user.id,
            AsyncJob.job_type == ASYNC_JOB_TYPE_PERSONAL_READING,
        )
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_async_job(job)


@router.get("/personal/history")
async def get_reading_history(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, le=50),
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    """Get past personal readings, paginated."""
    offset = (page - 1) * per_page
    result = await db.execute(
        select(PersonalReading)
        .where(PersonalReading.user_id == user.id)
        .order_by(PersonalReading.date_context.desc())
        .offset(offset)
        .limit(per_page)
    )
    readings = result.scalars().all()
    include_template_version = await _can_force_refresh_reading(user, db)
    return [
        _reading_payload(
            r,
            include_template_version=include_template_version,
        )
        for r in readings
    ]


@router.get("/personal/{date_str}")
async def get_reading_by_date(
    date_str: str,
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific date's personal reading."""
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    result = await db.execute(
        select(PersonalReading)
        .where(
            PersonalReading.user_id == user.id,
            PersonalReading.date_context == target,
        )
        .order_by(PersonalReading.created_at.desc())
        .limit(1)
    )
    reading = result.scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="No reading for this date")

    include_template_version = await _can_force_refresh_reading(user, db)
    return _reading_payload(reading, include_template_version=include_template_version)
