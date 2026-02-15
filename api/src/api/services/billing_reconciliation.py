"""Stripe billing reconciliation service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AnalyticsEvent, Subscription

from api.services.stripe_service import _get_stripe_client

logger = logging.getLogger(__name__)


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _extract_price_id(stripe_sub: dict[str, Any]) -> str | None:
    items = stripe_sub.get("items", {}).get("data", [])
    if not items:
        return None
    return items[0].get("price", {}).get("id")


async def run_billing_reconciliation(
    db: AsyncSession,
    *,
    trigger: str = "manual",
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    try:
        stripe_client = _get_stripe_client()
    except RuntimeError as exc:
        summary = {
            "status": "skipped",
            "reason": str(exc),
            "trigger": trigger,
            "started_at": started_at.isoformat(),
        }
        db.add(AnalyticsEvent(event_type="billing.reconciliation.skipped", metadata_json=summary))
        return summary

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id.is_not(None))
    )
    subscriptions = result.scalars().all()

    scanned = 0
    updated = 0
    failures = 0
    missing = 0

    for sub in subscriptions:
        scanned += 1
        stripe_sub_id = str(sub.stripe_subscription_id or "").strip()
        if not stripe_sub_id:
            continue

        try:
            stripe_sub = stripe_client.Subscription.retrieve(stripe_sub_id)
        except Exception as exc:
            failures += 1
            logger.warning("Billing reconciliation failed for %s: %s", stripe_sub_id, exc)
            continue

        if not stripe_sub:
            missing += 1
            continue

        changed = False
        next_status = str(stripe_sub.get("status") or "").strip() or sub.status
        if sub.status != next_status:
            sub.status = next_status
            changed = True

        next_price_id = _extract_price_id(stripe_sub)
        if sub.stripe_price_id != next_price_id:
            sub.stripe_price_id = next_price_id
            changed = True

        next_period_start = _as_datetime(stripe_sub.get("current_period_start"))
        if sub.current_period_start != next_period_start:
            sub.current_period_start = next_period_start
            changed = True

        next_period_end = _as_datetime(stripe_sub.get("current_period_end"))
        if sub.current_period_end != next_period_end:
            sub.current_period_end = next_period_end
            changed = True

        next_cancel_at_period_end = bool(stripe_sub.get("cancel_at_period_end", False))
        if sub.cancel_at_period_end != next_cancel_at_period_end:
            sub.cancel_at_period_end = next_cancel_at_period_end
            changed = True

        next_canceled_at = _as_datetime(stripe_sub.get("canceled_at"))
        if sub.canceled_at != next_canceled_at:
            sub.canceled_at = next_canceled_at
            changed = True

        if changed:
            sub.updated_at = datetime.now(UTC)
            updated += 1

    summary = {
        "status": "ok",
        "trigger": trigger,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "scanned": scanned,
        "updated": updated,
        "missing": missing,
        "failures": failures,
    }
    db.add(AnalyticsEvent(event_type="billing.reconciliation.run", metadata_json=summary))
    return summary
