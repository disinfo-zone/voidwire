"""Async job queue helpers + worker loop."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.database import get_session
from voidwire.models import AsyncJob, User

from api.services.personal_reading_service import PersonalReadingService

logger = logging.getLogger(__name__)

ASYNC_JOB_TYPE_PERSONAL_READING = "personal_reading.generate"
TERMINAL_JOB_STATUSES = {"completed", "failed"}


def serialize_async_job(job: AsyncJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "user_id": str(job.user_id),
        "job_type": job.job_type,
        "status": job.status,
        "payload": job.payload or {},
        "result": job.result,
        "error_message": job.error_message,
        "attempts": int(job.attempts or 0),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


async def enqueue_personal_reading_job(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    tier: str,
    target_date: date,
) -> AsyncJob:
    payload = {
        "tier": tier,
        "target_date": target_date.isoformat(),
    }

    # Deduplicate active jobs for same user/tier/day.
    existing_result = await db.execute(
        select(AsyncJob).where(
            AsyncJob.user_id == user_id,
            AsyncJob.job_type == ASYNC_JOB_TYPE_PERSONAL_READING,
            AsyncJob.status.in_(("queued", "running")),
            AsyncJob.payload["tier"].astext == tier,  # type: ignore[index]
            AsyncJob.payload["target_date"].astext == target_date.isoformat(),  # type: ignore[index]
        )
    )
    existing = existing_result.scalars().first()
    if existing:
        return existing

    job = AsyncJob(
        user_id=user_id,
        job_type=ASYNC_JOB_TYPE_PERSONAL_READING,
        status="queued",
        payload=payload,
        attempts=0,
    )
    db.add(job)
    await db.flush()
    return job


async def _claim_next_job(db: AsyncSession) -> AsyncJob | None:
    result = await db.execute(
        select(AsyncJob)
        .where(AsyncJob.status == "queued")
        .order_by(AsyncJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalars().first()
    if not job:
        return None
    job.status = "running"
    job.started_at = datetime.now(UTC)
    job.attempts = int(job.attempts or 0) + 1
    job.error_message = None
    return job


async def _process_personal_reading_job(db: AsyncSession, job: AsyncJob) -> dict[str, Any]:
    payload = job.payload or {}
    tier = str(payload.get("tier", "free")).strip().lower()
    target_date_raw = str(payload.get("target_date", "")).strip()
    if tier not in {"free", "pro"}:
        raise ValueError("Unsupported personal reading tier")

    try:
        target_date = date.fromisoformat(target_date_raw) if target_date_raw else date.today()
    except ValueError as exc:
        raise ValueError("Invalid target_date in job payload") from exc

    user = await db.get(User, job.user_id)
    if not user or not user.is_active:
        raise ValueError("User not found or inactive")
    if not user.profile:
        raise ValueError("User profile is missing")

    if tier == "pro":
        reading = await PersonalReadingService.get_or_generate_pro_reading(user, db)
    else:
        reading = await PersonalReadingService.get_or_generate_free_reading(user, db)

    if reading is None:
        raise RuntimeError("Failed to generate personal reading")

    return {
        "reading_id": str(reading.id) if getattr(reading, "id", None) else None,
        "tier": tier,
        "date_context": target_date.isoformat(),
    }


async def _process_job(db: AsyncSession, job: AsyncJob) -> None:
    if job.job_type != ASYNC_JOB_TYPE_PERSONAL_READING:
        raise ValueError(f"Unsupported job type: {job.job_type}")

    result = await _process_personal_reading_job(db, job)
    job.result = result


async def process_next_queued_job() -> bool:
    async with get_session() as db:
        job = await _claim_next_job(db)
        if not job:
            return False
        try:
            await _process_job(db, job)
            job.status = "completed"
            job.finished_at = datetime.now(UTC)
        except Exception as exc:
            logger.exception("Async job %s failed", job.id)
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)
        return True


async def run_async_job_worker(
    stop_event: asyncio.Event,
    *,
    poll_interval_seconds: float = 2.0,
) -> None:
    logger.info("Async job worker started")
    try:
        while not stop_event.is_set():
            had_work = False
            try:
                had_work = await process_next_queued_job()
            except Exception:
                logger.exception("Async job worker iteration failed")

            if not had_work:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=poll_interval_seconds)
                except TimeoutError:
                    pass
    finally:
        logger.info("Async job worker stopped")
