"""Stripe webhook handler."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AnalyticsEvent, StripeWebhookEvent, Subscription, User

from api.dependencies import get_db
from api.services.stripe_config import resolve_stripe_runtime_config
from api.services.stripe_service import verify_webhook_signature

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


async def _upsert_subscription(
    db: AsyncSession,
    stripe_sub: dict,
    stripe_customer_id: str,
) -> None:
    """Create or update a local Subscription record from Stripe data."""
    stripe_sub_id = stripe_sub["id"]

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalars().first()

    if not sub:
        # Find user by customer ID
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id)
        )
        existing = result.scalars().first()
        user_id = existing.user_id if existing else None

        if not user_id:
            # Try to find user from Stripe customer metadata
            customer_meta = stripe_sub.get("metadata", {})
            uid = customer_meta.get("user_id")
            if uid:
                user = await db.get(User, uid)
                user_id = user.id if user else None

        if not user_id:
            logger.warning("Cannot find user for Stripe customer %s", stripe_customer_id)
            return

        sub = Subscription(
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_sub_id,
        )
        db.add(sub)

    # Update fields from Stripe
    sub.status = stripe_sub.get("status", sub.status)
    sub.stripe_price_id = _extract_price_id(stripe_sub)
    sub.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)

    period_start = stripe_sub.get("current_period_start")
    if period_start:
        sub.current_period_start = datetime.fromtimestamp(period_start, tz=UTC)
    period_end = stripe_sub.get("current_period_end")
    if period_end:
        sub.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)

    canceled_at = stripe_sub.get("canceled_at")
    if canceled_at:
        sub.canceled_at = datetime.fromtimestamp(canceled_at, tz=UTC)

    # Determine billing interval
    items = stripe_sub.get("items", {}).get("data", [])
    if items:
        plan = items[0].get("plan", {})
        sub.billing_interval = plan.get("interval")

    sub.updated_at = datetime.now(UTC)
    await db.flush()


async def _register_webhook_event(
    db: AsyncSession,
    stripe_event_id: str,
    event_type: str,
) -> bool:
    """Persist webhook event ID; return False if already processed."""
    existing = await db.execute(
        select(StripeWebhookEvent.id).where(StripeWebhookEvent.stripe_event_id == stripe_event_id)
    )
    if existing.scalars().first() is not None:
        return False

    db.add(StripeWebhookEvent(stripe_event_id=stripe_event_id, event_type=event_type))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False
    return True


def _extract_price_id(stripe_sub: dict) -> str | None:
    items = stripe_sub.get("items", {}).get("data", [])
    if items:
        return items[0].get("price", {}).get("id")
    return None


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    stripe_config = await resolve_stripe_runtime_config(db)

    try:
        event = verify_webhook_signature(
            payload,
            sig_header,
            webhook_secret=str(stripe_config.get("webhook_secret") or "").strip(),
            secret_key=str(stripe_config.get("secret_key") or "").strip(),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        db.add(
            AnalyticsEvent(
                event_type="stripe.webhook.error",
                metadata_json={"reason": "invalid_signature"},
            )
        )
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_id = str(event.get("id", "")).strip()
    if not event_id:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    event_type = str(event.get("type", "")).strip()
    if not event_type:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    event_data = event.get("data")
    if not isinstance(event_data, dict) or not isinstance(event_data.get("object"), dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    data = event_data["object"]

    if not await _register_webhook_event(db, event_id, event_type):
        logger.info("Stripe duplicate webhook ignored: %s", event_id)
        db.add(
            AnalyticsEvent(
                event_type="stripe.webhook.duplicate",
                metadata_json={"event_type": event_type},
            )
        )
        return {"status": "duplicate_ignored"}

    logger.info("Stripe webhook: %s", event_type)

    if event_type == "checkout.session.completed":
        # Checkout completed - subscription will be created separately
        stripe_sub_id = data.get("subscription")
        stripe_customer_id = data.get("customer")
        user_id_meta = data.get("metadata", {}).get("user_id")

        if stripe_sub_id and stripe_customer_id and user_id_meta:
            user_id = _parse_uuid(user_id_meta)
            if user_id is None:
                logger.warning(
                    "Invalid user_id metadata in checkout.session.completed: %s",
                    user_id_meta,
                )
                return {"status": "ok"}

            user = await db.get(User, user_id)
            if user is None:
                logger.warning(
                    "Unknown user_id metadata in checkout.session.completed: %s",
                    user_id,
                )
                return {"status": "ok"}

            # Pre-create subscription record so we can link it
            result = await db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
            )
            if not result.scalars().first():
                sub = Subscription(
                    user_id=user_id,
                    stripe_customer_id=stripe_customer_id,
                    stripe_subscription_id=stripe_sub_id,
                    status="incomplete",
                )
                db.add(sub)
                await db.flush()

    elif event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        await _upsert_subscription(db, data, data.get("customer", ""))

    elif event_type == "invoice.payment_failed":
        sub_id = data.get("subscription")
        if sub_id:
            result = await db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
            )
            sub = result.scalars().first()
            if sub:
                sub.status = "past_due"
                sub.updated_at = datetime.now(UTC)

    elif event_type == "invoice.paid":
        sub_id = data.get("subscription")
        if sub_id:
            result = await db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
            )
            sub = result.scalars().first()
            if sub and sub.status == "past_due":
                sub.status = "active"
                sub.updated_at = datetime.now(UTC)

    db.add(
        AnalyticsEvent(
            event_type="stripe.webhook.processed",
            metadata_json={"event_type": event_type},
        )
    )

    return {"status": "ok"}
