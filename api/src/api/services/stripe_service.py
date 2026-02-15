"""Stripe SDK wrapper for subscription management."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import Subscription, User

logger = logging.getLogger(__name__)

try:
    import stripe as stripe_sdk
except ModuleNotFoundError:  # pragma: no cover - environment-dependent import
    stripe_sdk = None


def _get_stripe_client(*, require_secret_key: bool = True):
    if stripe_sdk is None:
        raise RuntimeError("Stripe SDK is not installed")
    settings = get_settings()
    if require_secret_key and not settings.stripe_secret_key:
        raise RuntimeError("Stripe is not configured")
    if settings.stripe_secret_key:
        stripe_sdk.api_key = settings.stripe_secret_key
    return stripe_sdk


async def get_or_create_customer(user: User, db: AsyncSession) -> str:
    """Get existing Stripe customer ID or create a new one."""
    stripe_client = _get_stripe_client()

    # Check if user already has a subscription with a customer ID
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id).limit(1)
    )
    existing = result.scalars().first()
    if existing:
        return existing.stripe_customer_id

    # Create new Stripe customer
    customer = stripe_client.Customer.create(
        email=user.email,
        metadata={"user_id": str(user.id)},
    )
    return customer["id"]


def create_checkout_session(
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    promotion_code_id: str | None = None,
) -> str:
    """Create a Stripe Checkout session, return the URL."""
    stripe_client = _get_stripe_client()
    session_payload: dict[str, object] = {
        "customer": customer_id,
        "payment_method_types": ["card"],
        "line_items": [{"price": price_id, "quantity": 1}],
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "allow_promotion_codes": True,
    }
    if promotion_code_id:
        session_payload["discounts"] = [{"promotion_code": promotion_code_id}]

    session = stripe_client.checkout.Session.create(
        **session_payload,
    )
    return session["url"]


def create_billing_portal_session(customer_id: str, return_url: str) -> str:
    """Create a Stripe Billing Portal session, return the URL."""
    stripe_client = _get_stripe_client()
    session = stripe_client.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session["url"]


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """Verify Stripe webhook signature and return parsed event."""
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise RuntimeError("Stripe webhook secret is not configured")
    stripe_client = _get_stripe_client(require_secret_key=False)
    return stripe_client.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )


def list_active_recurring_prices(limit: int = 10) -> list[dict]:
    """List active recurring Stripe prices."""
    stripe_client = _get_stripe_client()
    prices = stripe_client.Price.list(active=True, type="recurring", limit=limit)
    return list(prices.get("data", []))


def is_price_active_recurring(price_id: str) -> bool:
    """Check whether a Stripe price is active and recurring."""
    stripe_client = _get_stripe_client()
    price = stripe_client.Price.retrieve(price_id)
    recurring = price.get("recurring")
    return bool(price.get("active") and recurring)


def create_coupon_and_promotion_code(
    *,
    code: str,
    percent_off: float | None,
    amount_off_cents: int | None,
    currency: str | None,
    duration: str,
    duration_in_months: int | None,
    max_redemptions: int | None,
    expires_at: datetime | None,
) -> dict[str, str]:
    """Create a Stripe coupon + promotion code pair."""
    stripe_client = _get_stripe_client()
    coupon_payload: dict[str, object] = {"duration": duration}
    if percent_off is not None:
        coupon_payload["percent_off"] = percent_off
    elif amount_off_cents is not None and currency:
        coupon_payload["amount_off"] = amount_off_cents
        coupon_payload["currency"] = currency
    else:
        raise RuntimeError("Either percent_off or amount_off_cents/currency is required")

    if duration == "repeating" and duration_in_months is not None:
        coupon_payload["duration_in_months"] = duration_in_months

    coupon = stripe_client.Coupon.create(**coupon_payload)
    promo_payload: dict[str, object] = {"coupon": coupon["id"], "code": code, "active": True}
    if max_redemptions is not None:
        promo_payload["max_redemptions"] = max_redemptions
    if expires_at is not None:
        normalized = (
            expires_at.astimezone(UTC)
            if expires_at.tzinfo
            else expires_at.replace(tzinfo=UTC)
        )
        promo_payload["expires_at"] = int(normalized.timestamp())

    promotion_code = stripe_client.PromotionCode.create(**promo_payload)
    return {
        "stripe_coupon_id": str(coupon["id"]),
        "stripe_promotion_code_id": str(promotion_code["id"]),
    }


def set_promotion_code_active(promotion_code_id: str, *, active: bool) -> None:
    """Activate or deactivate a Stripe promotion code."""
    stripe_client = _get_stripe_client()
    stripe_client.PromotionCode.modify(promotion_code_id, active=active)


def map_checkout_exception(exc: Exception) -> tuple[int, str]:
    """Map Stripe checkout errors to actionable client-safe messages."""
    message = str(exc).strip()
    lowered = message.lower()

    if "promotion code" in lowered or "coupon" in lowered or "discount" in lowered:
        if "expired" in lowered:
            return 400, "Discount code has expired"
        if "max redemption" in lowered or "max redemptions" in lowered:
            return 400, "Discount code has reached its redemption limit"
        if "inactive" in lowered or "not active" in lowered:
            return 400, "Discount code is no longer active"
        if "no such" in lowered or "invalid" in lowered:
            return 400, "Discount code is invalid"
        return 400, "Discount code cannot be applied"

    if "no such price" in lowered or "price" in lowered and "invalid" in lowered:
        return 400, "Selected plan is no longer available"

    if "customer" in lowered and ("invalid" in lowered or "no such" in lowered):
        return 400, "Unable to start checkout for this account"

    if message:
        logger.warning("Stripe checkout error: %s", message)
    else:
        logger.warning("Stripe checkout error: %s", exc.__class__.__name__)
    return 503, "Unable to create checkout session. Please try again shortly."
