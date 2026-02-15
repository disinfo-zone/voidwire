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
    EmailVerificationToken,
    PasswordResetToken,
    PipelineRun,
    StripeWebhookEvent,
    User,
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
