"""Admin analytics."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import (
    AdminUser,
    AnalyticsEvent,
    AsyncJob,
    BatchRun,
    EmailVerificationToken,
    PasswordResetToken,
    PersonalReading,
    PipelineRun,
    Reading,
    StripeWebhookEvent,
    Subscription,
    User,
    UserProfile,
)

from api.dependencies import get_db, require_admin

router = APIRouter()


@router.get("/events")
async def get_analytics(
    days: int = Query(default=30),
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    del user
    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(
        select(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
        .where(AnalyticsEvent.created_at >= cutoff)
        .group_by(AnalyticsEvent.event_type)
    )
    return [{"event_type": row[0], "count": row[1]} for row in result.all()]


@router.get("/pipeline-health")
async def get_pipeline_health(
    days: int = Query(default=30),
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    del user
    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(
        select(PipelineRun.status, func.count(PipelineRun.id))
        .where(PipelineRun.date_context >= cutoff)
        .group_by(PipelineRun.status)
    )
    return [{"status": row[0], "count": row[1]} for row in result.all()]


@router.get("/batch-runs")
async def get_batch_runs(
    batch_type: str | None = Query(default=None),
    days: int = Query(default=30),
    limit: int = Query(default=50),
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    del user
    cutoff = datetime.now(UTC) - timedelta(days=days)
    query = select(BatchRun).where(BatchRun.started_at >= cutoff)
    if batch_type:
        query = query.where(BatchRun.batch_type == batch_type)
    query = query.order_by(BatchRun.started_at.desc()).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()
    return [
        {
            "id": str(run.id),
            "batch_type": run.batch_type,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            "status": run.status,
            "target_date": run.target_date.isoformat() if run.target_date else None,
            "week_key": run.week_key,
            "eligible_count": run.eligible_count,
            "skipped_count": run.skipped_count,
            "generated_count": run.generated_count,
            "error_count": run.error_count,
            "non_latin_fix_count": run.non_latin_fix_count,
            "summary_json": run.summary_json,
            "error_detail": run.error_detail,
        }
        for run in runs
    ]


@router.get("/kpis")
async def get_kpis(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    del user
    now = datetime.now(UTC)
    today = date.today()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    total_users = int((await db.execute(select(func.count(User.id)))).scalar() or 0)
    new_users_7d = int(
        (
            await db.execute(
                select(func.count(User.id)).where(User.created_at >= week_ago)
            )
        ).scalar()
        or 0
    )
    email_verified_users = int(
        (
            await db.execute(
                select(func.count(User.id)).where(User.email_verified.is_(True))
            )
        ).scalar()
        or 0
    )
    users_with_profile = int((await db.execute(select(func.count(UserProfile.user_id)))).scalar() or 0)

    active_subscribers = int(
        (
            await db.execute(
                select(func.count(func.distinct(Subscription.user_id))).where(
                    Subscription.status.in_(("active", "trialing")),
                )
            )
        ).scalar()
        or 0
    )
    trialing_subscribers = int(
        (
            await db.execute(
                select(func.count(func.distinct(Subscription.user_id))).where(
                    Subscription.status == "trialing",
                )
            )
        ).scalar()
        or 0
    )
    past_due_subscribers = int(
        (
            await db.execute(
                select(func.count(func.distinct(Subscription.user_id))).where(
                    Subscription.status == "past_due",
                )
            )
        ).scalar()
        or 0
    )
    canceled_subscribers = int(
        (
            await db.execute(
                select(func.count(func.distinct(Subscription.user_id))).where(
                    Subscription.status == "canceled",
                )
            )
        ).scalar()
        or 0
    )
    manual_pro_overrides = int(
        (
            await db.execute(
                select(func.count(User.id)).where(
                    User.pro_override.is_(True),
                    (User.pro_override_until.is_(None)) | (User.pro_override_until > now),
                )
            )
        ).scalar()
        or 0
    )
    test_users = int(
        (
            await db.execute(
                select(func.count(User.id)).where(
                    User.pro_override_reason.is_not(None),
                    func.lower(User.pro_override_reason).like("%test%"),
                )
            )
        ).scalar()
        or 0
    )

    active_sub_ids = select(Subscription.user_id.label("user_id")).where(
        Subscription.status.in_(("active", "trialing"))
    )
    override_ids = select(User.id.label("user_id")).where(
        User.pro_override.is_(True),
        (User.pro_override_until.is_(None)) | (User.pro_override_until > now),
    )
    pro_union = active_sub_ids.union(override_ids).subquery()
    pro_users_total = int(
        (await db.execute(select(func.count()).select_from(pro_union))).scalar() or 0
    )

    personal_generated_total = int(
        (await db.execute(select(func.count(PersonalReading.id)))).scalar() or 0
    )
    personal_generated_24h = int(
        (
            await db.execute(
                select(func.count(PersonalReading.id)).where(PersonalReading.created_at >= day_ago)
            )
        ).scalar()
        or 0
    )
    personal_generated_today = int(
        (
            await db.execute(
                select(func.count(PersonalReading.id)).where(PersonalReading.date_context == today)
            )
        ).scalar()
        or 0
    )
    personal_pro_today = int(
        (
            await db.execute(
                select(func.count(PersonalReading.id)).where(
                    PersonalReading.tier == "pro",
                    PersonalReading.date_context == today,
                )
            )
        ).scalar()
        or 0
    )

    job_counts_result = await db.execute(
        select(AsyncJob.status, func.count(AsyncJob.id))
        .where(
            AsyncJob.job_type == "personal_reading.generate",
            AsyncJob.created_at >= day_ago,
        )
        .group_by(AsyncJob.status)
    )
    job_counts = {str(status): int(count) for status, count in job_counts_result.all()}

    pipeline_counts_result = await db.execute(
        select(PipelineRun.status, func.count(PipelineRun.id))
        .where(PipelineRun.date_context >= (today - timedelta(days=6)))
        .group_by(PipelineRun.status)
    )
    pipeline_counts = {str(status): int(count) for status, count in pipeline_counts_result.all()}

    published_30d = int(
        (
            await db.execute(
                select(func.count(Reading.id)).where(
                    Reading.status == "published",
                    Reading.date_context >= (today - timedelta(days=29)),
                )
            )
        ).scalar()
        or 0
    )

    # -- Batch run KPIs --
    last_free_result = await db.execute(
        select(BatchRun)
        .where(BatchRun.batch_type == "free_reading")
        .order_by(BatchRun.started_at.desc())
        .limit(1)
    )
    last_free = last_free_result.scalars().first()
    last_pro_result = await db.execute(
        select(BatchRun)
        .where(BatchRun.batch_type == "pro_reading")
        .order_by(BatchRun.started_at.desc())
        .limit(1)
    )
    last_pro = last_pro_result.scalars().first()

    batch_7d_cutoff = now - timedelta(days=7)
    batch_7d_result = await db.execute(
        select(BatchRun).where(BatchRun.started_at >= batch_7d_cutoff)
    )
    batch_7d_runs = batch_7d_result.scalars().all()
    batches_7d = {
        "completed": sum(1 for r in batch_7d_runs if r.status == "completed"),
        "failed": sum(1 for r in batch_7d_runs if r.status == "failed"),
        "total_generated": sum(r.generated_count for r in batch_7d_runs),
        "total_errors": sum(r.error_count for r in batch_7d_runs),
        "total_non_latin_fixes": sum(r.non_latin_fix_count for r in batch_7d_runs),
    }

    def _batch_summary(br: BatchRun | None) -> dict | None:
        if not br:
            return None
        return {
            "status": br.status,
            "generated_count": br.generated_count,
            "started_at": br.started_at.isoformat() if br.started_at else None,
            "ended_at": br.ended_at.isoformat() if br.ended_at else None,
        }

    return {
        "generated_at": now.isoformat(),
        "users": {
            "total": total_users,
            "new_7d": new_users_7d,
            "email_verified": email_verified_users,
            "with_profile": users_with_profile,
            "pro_total": pro_users_total,
            "active_subscribers": active_subscribers,
            "manual_overrides": manual_pro_overrides,
            "test_accounts": test_users,
        },
        "subscriptions": {
            "active_or_trialing": active_subscribers,
            "trialing": trialing_subscribers,
            "past_due": past_due_subscribers,
            "canceled": canceled_subscribers,
        },
        "personal_readings": {
            "generated_total": personal_generated_total,
            "generated_24h": personal_generated_24h,
            "generated_today": personal_generated_today,
            "pro_generated_today": personal_pro_today,
        },
        "jobs_24h": {
            "queued": int(job_counts.get("queued", 0)),
            "running": int(job_counts.get("running", 0)),
            "completed": int(job_counts.get("completed", 0)),
            "failed": int(job_counts.get("failed", 0)),
        },
        "pipeline_7d": {
            "completed": int(pipeline_counts.get("completed", 0)),
            "failed": int(pipeline_counts.get("failed", 0)),
            "running": int(pipeline_counts.get("running", 0)),
            "published_readings_30d": published_30d,
        },
        "batches": {
            "last_free_batch": _batch_summary(last_free),
            "last_pro_batch": _batch_summary(last_pro),
            "batches_7d": batches_7d,
        },
    }


@router.get("/operational-health")
async def get_operational_health(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    del user
    now = datetime.now(UTC)
    alerts: list[dict[str, str]] = []

    # Webhook freshness SLO
    latest_webhook_result = await db.execute(
        select(StripeWebhookEvent.received_at)
        .order_by(StripeWebhookEvent.received_at.desc())
        .limit(1)
    )
    latest_webhook_at = latest_webhook_result.scalars().first()
    webhook_lag_minutes = None
    webhook_status = "ok"
    if latest_webhook_at:
        webhook_lag_minutes = round((now - latest_webhook_at).total_seconds() / 60, 2)
        if webhook_lag_minutes > 120:
            webhook_status = "critical"
            alerts.append(
                {
                    "severity": "critical",
                    "code": "webhook_lag",
                    "message": f"Latest Stripe webhook is {webhook_lag_minutes} minutes old",
                }
            )
        elif webhook_lag_minutes > 30:
            webhook_status = "warn"
            alerts.append(
                {
                    "severity": "warn",
                    "code": "webhook_lag",
                    "message": f"Latest Stripe webhook is {webhook_lag_minutes} minutes old",
                }
            )
    elif get_settings().stripe_secret_key:
        webhook_status = "warn"
        alerts.append(
            {
                "severity": "warn",
                "code": "webhook_missing",
                "message": "No Stripe webhook events have been recorded yet",
            }
        )

    # Checkout failure-rate SLO over 24h
    checkout_cutoff = now - timedelta(hours=24)
    checkout_success_result = await db.execute(
        select(func.count(AnalyticsEvent.id)).where(
            AnalyticsEvent.event_type == "checkout.success",
            AnalyticsEvent.created_at >= checkout_cutoff,
        )
    )
    checkout_failure_result = await db.execute(
        select(func.count(AnalyticsEvent.id)).where(
            AnalyticsEvent.event_type == "checkout.failure",
            AnalyticsEvent.created_at >= checkout_cutoff,
        )
    )
    checkout_success = int(checkout_success_result.scalar() or 0)
    checkout_failure = int(checkout_failure_result.scalar() or 0)
    checkout_total = checkout_success + checkout_failure
    checkout_failure_rate = (
        round((checkout_failure / checkout_total) * 100, 2) if checkout_total else 0.0
    )
    checkout_status = "ok"
    if checkout_total >= 5 and checkout_failure_rate >= 20:
        checkout_status = "critical"
        alerts.append(
            {
                "severity": "critical",
                "code": "checkout_failure_rate",
                "message": f"Checkout failure rate is {checkout_failure_rate}% over the last 24h",
            }
        )
    elif checkout_total >= 5 and checkout_failure_rate >= 10:
        checkout_status = "warn"
        alerts.append(
            {
                "severity": "warn",
                "code": "checkout_failure_rate",
                "message": f"Checkout failure rate is {checkout_failure_rate}% over the last 24h",
            }
        )

    # Token cleanup health
    stale_email_result = await db.execute(
        select(func.count(EmailVerificationToken.id)).where(
            (EmailVerificationToken.expires_at <= now)
            | (EmailVerificationToken.used_at.is_not(None))
        )
    )
    stale_password_result = await db.execute(
        select(func.count(PasswordResetToken.id)).where(
            (PasswordResetToken.expires_at <= now) | (PasswordResetToken.used_at.is_not(None))
        )
    )
    stale_email_tokens = int(stale_email_result.scalar() or 0)
    stale_password_tokens = int(stale_password_result.scalar() or 0)
    stale_tokens_total = stale_email_tokens + stale_password_tokens

    latest_cleanup_result = await db.execute(
        select(AnalyticsEvent.created_at)
        .where(AnalyticsEvent.event_type == "auth.token_cleanup")
        .order_by(AnalyticsEvent.created_at.desc())
        .limit(1)
    )
    latest_cleanup_at = latest_cleanup_result.scalars().first()
    cleanup_age_minutes = (
        round((now - latest_cleanup_at).total_seconds() / 60, 2) if latest_cleanup_at else None
    )

    token_cleanup_status = "ok"
    if stale_tokens_total >= 100:
        token_cleanup_status = "critical"
        alerts.append(
            {
                "severity": "critical",
                "code": "token_cleanup_backlog",
                "message": f"Token cleanup backlog has {stale_tokens_total} stale rows",
            }
        )
    elif stale_tokens_total > 0:
        token_cleanup_status = "warn"
        alerts.append(
            {
                "severity": "warn",
                "code": "token_cleanup_backlog",
                "message": f"Token cleanup backlog has {stale_tokens_total} stale rows",
            }
        )

    # Manual pro override hygiene
    expired_override_result = await db.execute(
        select(func.count(User.id)).where(
            User.pro_override.is_(True),
            User.pro_override_until.is_not(None),
            User.pro_override_until <= now,
        )
    )
    expiring_24h_result = await db.execute(
        select(func.count(User.id)).where(
            User.pro_override.is_(True),
            User.pro_override_until.is_not(None),
            User.pro_override_until > now,
            User.pro_override_until <= now + timedelta(hours=24),
        )
    )
    perpetual_override_result = await db.execute(
        select(func.count(User.id)).where(
            User.pro_override.is_(True),
            User.pro_override_until.is_(None),
        )
    )
    expired_overrides = int(expired_override_result.scalar() or 0)
    expiring_24h = int(expiring_24h_result.scalar() or 0)
    perpetual_overrides = int(perpetual_override_result.scalar() or 0)

    override_status = "ok"
    if expired_overrides > 0:
        override_status = "warn"
        alerts.append(
            {
                "severity": "warn",
                "code": "expired_pro_overrides",
                "message": f"{expired_overrides} manual pro overrides are past expiration",
            }
        )

    overall_status = "ok"
    if any(alert["severity"] == "critical" for alert in alerts):
        overall_status = "critical"
    elif alerts:
        overall_status = "warn"

    return {
        "status": overall_status,
        "generated_at": now.isoformat(),
        "alerts": alerts,
        "slo": {
            "webhook_freshness_30m": {
                "status": webhook_status,
                "latest_webhook_at": (latest_webhook_at.isoformat() if latest_webhook_at else None),
                "lag_minutes": webhook_lag_minutes,
            },
            "checkout_failure_rate_10pct_24h": {
                "status": checkout_status,
                "success_count": checkout_success,
                "failure_count": checkout_failure,
                "failure_rate_percent": checkout_failure_rate,
            },
            "token_cleanup_backlog_zero": {
                "status": token_cleanup_status,
                "stale_email_tokens": stale_email_tokens,
                "stale_password_tokens": stale_password_tokens,
                "latest_cleanup_at": latest_cleanup_at.isoformat() if latest_cleanup_at else None,
                "cleanup_age_minutes": cleanup_age_minutes,
            },
            "pro_override_hygiene": {
                "status": override_status,
                "expired_overrides": expired_overrides,
                "expiring_within_24h": expiring_24h,
                "perpetual_overrides": perpetual_overrides,
            },
        },
    }
