"""Data governance helpers (retention cleanup, lifecycle hygiene)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import AnalyticsEvent, AsyncJob, EmailVerificationToken, PasswordResetToken


async def run_retention_cleanup(
    db: AsyncSession,
    *,
    trigger: str = "manual",
) -> dict[str, Any]:
    settings = get_settings()
    now = datetime.now(UTC)

    email_deleted = (
        await db.execute(
            delete(EmailVerificationToken).where(
                (EmailVerificationToken.expires_at <= now)
                | (EmailVerificationToken.used_at.is_not(None))
            )
        )
    ).rowcount or 0

    password_deleted = (
        await db.execute(
            delete(PasswordResetToken).where(
                (PasswordResetToken.expires_at <= now)
                | (PasswordResetToken.used_at.is_not(None))
            )
        )
    ).rowcount or 0

    async_job_cutoff = now - timedelta(days=max(1, int(settings.async_job_retention_days)))
    async_jobs_deleted = (
        await db.execute(
            delete(AsyncJob).where(
                AsyncJob.status.in_(("completed", "failed")),
                AsyncJob.finished_at.is_not(None),
                AsyncJob.finished_at < async_job_cutoff,
            )
        )
    ).rowcount or 0

    analytics_cutoff = now - timedelta(days=max(1, int(settings.analytics_retention_days)))
    analytics_deleted = (
        await db.execute(
            delete(AnalyticsEvent).where(AnalyticsEvent.created_at < analytics_cutoff)
        )
    ).rowcount or 0

    summary = {
        "status": "ok",
        "trigger": trigger,
        "ran_at": now.isoformat(),
        "email_tokens_deleted": int(email_deleted),
        "password_tokens_deleted": int(password_deleted),
        "async_jobs_deleted": int(async_jobs_deleted),
        "analytics_deleted": int(analytics_deleted),
        "async_job_cutoff": async_job_cutoff.isoformat(),
        "analytics_cutoff": analytics_cutoff.isoformat(),
    }
    db.add(AnalyticsEvent(event_type="retention.cleanup", metadata_json=summary))
    return summary

