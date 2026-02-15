"""User subscription management endpoints."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import AnalyticsEvent, User

from api.dependencies import get_current_public_user, get_db
from api.services.discount_code_service import resolve_usable_discount_code
from api.services.stripe_service import (
    create_billing_portal_session,
    create_checkout_session,
    get_or_create_customer,
    is_price_active_recurring,
    list_active_recurring_prices,
    map_checkout_exception,
)
from api.services.subscription_service import get_user_tier

router = APIRouter()


class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str
    discount_code: str | None = Field(default=None, max_length=32)


class PortalRequest(BaseModel):
    return_url: str


def _origin(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".lower()


def _validate_redirect_url(url: str, *, field_name: str) -> str:
    settings = get_settings()
    allowed_origins = {_origin(settings.site_url), _origin(settings.admin_url)}
    allowed_origins.discard(None)

    parsed_origin = _origin(url)
    if parsed_origin is None or parsed_origin not in allowed_origins:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}: URL must match configured site/admin origin",
        )
    return url


def _track_checkout_event(
    db: AsyncSession,
    *,
    event_type: str,
    user_id: str,
    price_id: str,
    discount_code: str | None,
    detail: str | None = None,
) -> None:
    db.add(
        AnalyticsEvent(
            event_type=event_type,
            metadata_json={
                "user_id": user_id,
                "price_id": price_id,
                "discount_code": discount_code,
                "detail": detail,
            },
        )
    )


@router.get("/")
async def get_subscription_status(
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current subscription status."""
    tier = await get_user_tier(user, db)

    # Find active subscription details
    active_sub = None
    for sub in user.subscriptions:
        if sub.status in ("active", "trialing"):
            active_sub = sub
            break

    if not active_sub:
        return {"tier": tier, "subscription": None}

    return {
        "tier": tier,
        "subscription": {
            "status": active_sub.status,
            "billing_interval": active_sub.billing_interval,
            "current_period_end": (
                active_sub.current_period_end.isoformat() if active_sub.current_period_end else None
            ),
            "cancel_at_period_end": active_sub.cancel_at_period_end,
        },
    }


@router.post("/checkout")
async def create_checkout(
    req: CheckoutRequest,
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for subscription."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=501, detail="Stripe not configured")

    success_url = _validate_redirect_url(req.success_url, field_name="success_url")
    cancel_url = _validate_redirect_url(req.cancel_url, field_name="cancel_url")

    normalized_discount_code = req.discount_code.strip().upper() if req.discount_code else None
    try:
        if not is_price_active_recurring(req.price_id):
            _track_checkout_event(
                db,
                event_type="checkout.failure",
                user_id=str(user.id),
                price_id=req.price_id,
                discount_code=normalized_discount_code,
                detail="invalid_price_id",
            )
            raise HTTPException(status_code=400, detail="Invalid price_id")

        promotion_code_id = None
        if normalized_discount_code:
            discount_code = await resolve_usable_discount_code(db, normalized_discount_code)
            if discount_code is None:
                _track_checkout_event(
                    db,
                    event_type="checkout.failure",
                    user_id=str(user.id),
                    price_id=req.price_id,
                    discount_code=normalized_discount_code,
                    detail="invalid_discount_code",
                )
                raise HTTPException(status_code=400, detail="Invalid or expired discount code")
            promotion_code_id = discount_code.stripe_promotion_code_id

        customer_id = await get_or_create_customer(user, db)
        url = create_checkout_session(
            customer_id=customer_id,
            price_id=req.price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            promotion_code_id=promotion_code_id,
        )
        _track_checkout_event(
            db,
            event_type="checkout.success",
            user_id=str(user.id),
            price_id=req.price_id,
            discount_code=normalized_discount_code,
        )
    except RuntimeError as exc:
        _track_checkout_event(
            db,
            event_type="checkout.failure",
            user_id=str(user.id),
            price_id=req.price_id,
            discount_code=normalized_discount_code,
            detail=str(exc),
        )
        raise HTTPException(status_code=503, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        status_code, detail = map_checkout_exception(exc)
        _track_checkout_event(
            db,
            event_type="checkout.failure",
            user_id=str(user.id),
            price_id=req.price_id,
            discount_code=normalized_discount_code,
            detail=detail,
        )
        raise HTTPException(status_code=status_code, detail=detail)
    return {"checkout_url": url}


@router.post("/portal")
async def create_portal(
    req: PortalRequest,
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Billing Portal session."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=501, detail="Stripe not configured")

    return_url = _validate_redirect_url(req.return_url, field_name="return_url")

    try:
        customer_id = await get_or_create_customer(user, db)
        url = create_billing_portal_session(
            customer_id=customer_id,
            return_url=return_url,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"portal_url": url}


@router.get("/prices")
async def get_prices():
    """Get available subscription prices."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        return {"prices": []}

    try:
        prices = list_active_recurring_prices(limit=10)
        return {
            "prices": [
                {
                    "id": p["id"],
                    "unit_amount": p["unit_amount"],
                    "currency": p["currency"],
                    "interval": p["recurring"]["interval"] if p.get("recurring") else None,
                    "product": p["product"],
                }
                for p in prices
            ],
            "publishable_key": settings.stripe_publishable_key,
        }
    except Exception:
        return {"prices": [], "publishable_key": settings.stripe_publishable_key}
