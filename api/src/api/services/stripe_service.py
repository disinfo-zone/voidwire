"""Stripe SDK wrapper for subscription management."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import Subscription, User

logger = logging.getLogger(__name__)

try:
    import stripe as stripe_sdk
except ModuleNotFoundError:  # pragma: no cover - environment-dependent import
    stripe_sdk = None


def _get_stripe_client(
    *,
    require_secret_key: bool = True,
    secret_key: str | None = None,
):
    if stripe_sdk is None:
        raise RuntimeError("Stripe SDK is not installed")
    settings = get_settings()
    effective_secret_key = str(secret_key or settings.stripe_secret_key or "").strip()
    if require_secret_key and not effective_secret_key:
        raise RuntimeError("Stripe is not configured")
    if effective_secret_key:
        stripe_sdk.api_key = effective_secret_key
    return stripe_sdk


def _mode_from_key(value: str) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("sk_test_") or normalized.startswith("pk_test_"):
        return "test"
    if normalized.startswith("sk_live_") or normalized.startswith("pk_live_"):
        return "live"
    return None


async def get_or_create_customer(
    user: User,
    db: AsyncSession,
    *,
    secret_key: str | None = None,
) -> str:
    """Get existing Stripe customer ID or create a new one."""
    stripe_client = _get_stripe_client(secret_key=secret_key)

    # Check if user already has a subscription with a customer ID
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id).limit(1))
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
    *,
    secret_key: str | None = None,
) -> str:
    """Create a Stripe Checkout session, return the URL."""
    stripe_client = _get_stripe_client(secret_key=secret_key)
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


def create_billing_portal_session(
    customer_id: str,
    return_url: str,
    *,
    secret_key: str | None = None,
) -> str:
    """Create a Stripe Billing Portal session, return the URL."""
    stripe_client = _get_stripe_client(secret_key=secret_key)
    session = stripe_client.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session["url"]


def verify_webhook_signature(
    payload: bytes,
    sig_header: str,
    *,
    webhook_secret: str | None = None,
    secret_key: str | None = None,
) -> dict:
    """Verify Stripe webhook signature and return parsed event."""
    settings = get_settings()
    effective_webhook_secret = str(webhook_secret or settings.stripe_webhook_secret or "").strip()
    if not effective_webhook_secret:
        raise RuntimeError("Stripe webhook secret is not configured")
    stripe_client = _get_stripe_client(require_secret_key=False, secret_key=secret_key)
    return stripe_client.Webhook.construct_event(
        payload,
        sig_header,
        effective_webhook_secret,
    )


def list_active_recurring_prices(limit: int = 10, *, secret_key: str | None = None) -> list[dict]:
    """List active recurring Stripe prices."""
    stripe_client = _get_stripe_client(secret_key=secret_key)
    prices = stripe_client.Price.list(
        active=True,
        type="recurring",
        limit=limit,
        expand=["data.product"],
    )
    return list(prices.get("data", []))


def is_price_active_recurring(price_id: str, *, secret_key: str | None = None) -> bool:
    """Check whether a Stripe price is active and recurring."""
    stripe_client = _get_stripe_client(secret_key=secret_key)
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
    secret_key: str | None = None,
) -> dict[str, str]:
    """Create a Stripe coupon + promotion code pair."""
    stripe_client = _get_stripe_client(secret_key=secret_key)
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
            expires_at.astimezone(UTC) if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        )
        promo_payload["expires_at"] = int(normalized.timestamp())

    promotion_code = stripe_client.PromotionCode.create(**promo_payload)
    return {
        "stripe_coupon_id": str(coupon["id"]),
        "stripe_promotion_code_id": str(promotion_code["id"]),
    }


def set_promotion_code_active(
    promotion_code_id: str,
    *,
    active: bool,
    secret_key: str | None = None,
) -> None:
    """Activate or deactivate a Stripe promotion code."""
    stripe_client = _get_stripe_client(secret_key=secret_key)
    stripe_client.PromotionCode.modify(promotion_code_id, active=active)


def run_stripe_connectivity_check(
    *,
    secret_key: str,
    publishable_key: str,
    webhook_secret: str | None,
    price_limit: int = 5,
) -> dict[str, Any]:
    """Validate Stripe key pair, account access, and recurring price visibility."""
    normalized_secret = str(secret_key or "").strip()
    normalized_publishable = str(publishable_key or "").strip()
    normalized_webhook = str(webhook_secret or "").strip()

    if not normalized_secret or not normalized_publishable:
        return {
            "status": "error",
            "message": "Stripe secret and publishable keys are required",
            "enabled": False,
            "key_mode_match": False,
            "webhook_ready": bool(normalized_webhook),
            "active_price_count": 0,
            "sample_prices": [],
            "warnings": [],
        }

    secret_mode = _mode_from_key(normalized_secret)
    publishable_mode = _mode_from_key(normalized_publishable)
    mode_match = bool(secret_mode and publishable_mode and secret_mode == publishable_mode)

    warnings: list[str] = []
    if secret_mode is None or publishable_mode is None:
        warnings.append("Could not infer key mode from key prefixes")
    elif not mode_match:
        warnings.append("Secret and publishable keys appear to be from different modes")
    if not normalized_webhook:
        warnings.append("Webhook secret is not configured")

    try:
        stripe_client = _get_stripe_client(secret_key=normalized_secret)
        account = stripe_client.Account.retrieve()
        prices = stripe_client.Price.list(
            active=True,
            type="recurring",
            limit=max(1, int(price_limit)),
            expand=["data.product"],
        )
    except RuntimeError as exc:
        return {
            "status": "error",
            "message": str(exc),
            "enabled": False,
            "key_mode_match": mode_match,
            "webhook_ready": bool(normalized_webhook),
            "active_price_count": 0,
            "sample_prices": [],
            "warnings": warnings,
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Stripe check failed: {str(exc).strip() or exc.__class__.__name__}",
            "enabled": False,
            "key_mode_match": mode_match,
            "webhook_ready": bool(normalized_webhook),
            "active_price_count": 0,
            "sample_prices": [],
            "warnings": warnings,
        }

    price_rows = list(prices.get("data", []))
    sample_prices = []
    for item in price_rows:
        product_name = ""
        if isinstance(item.get("product"), dict):
            product_name = str(item["product"].get("name") or "").strip()
        sample_prices.append(
            {
                "id": item.get("id"),
                "unit_amount": item.get("unit_amount"),
                "currency": item.get("currency"),
                "interval": item.get("recurring", {}).get("interval")
                if isinstance(item.get("recurring"), dict)
                else None,
                "product": product_name or item.get("product"),
                "nickname": item.get("nickname"),
            }
        )

    if len(price_rows) == 0:
        warnings.append("No active recurring prices found")

    api_mode = "live" if bool(account.get("livemode")) else "test"
    if secret_mode and api_mode != secret_mode:
        warnings.append("Stripe account mode does not match secret key prefix")

    status = "warning" if warnings else "ok"
    message = "Stripe connectivity check passed"
    if status == "warning":
        message = "Stripe check completed with warnings"

    return {
        "status": status,
        "message": message,
        "enabled": True,
        "account_id": account.get("id"),
        "api_mode": api_mode,
        "secret_key_mode": secret_mode,
        "publishable_key_mode": publishable_mode,
        "key_mode_match": mode_match,
        "webhook_ready": bool(normalized_webhook),
        "active_price_count": len(price_rows),
        "sample_prices": sample_prices,
        "warnings": warnings,
    }


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
