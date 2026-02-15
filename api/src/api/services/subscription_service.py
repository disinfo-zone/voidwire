"""Subscription tier determination."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import Subscription, User

ACTIVE_SUBSCRIPTION_STATUSES = ("active", "trialing")


def has_active_pro_override(user: User, now: datetime | None = None) -> bool:
    """Check whether a user has an active manual pro override."""
    if not bool(getattr(user, "pro_override", False)):
        return False
    expires_at = getattr(user, "pro_override_until", None)
    if expires_at is None:
        return True
    current = now or datetime.now(UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at > current


async def get_user_tier(user: User, db: AsyncSession) -> str:
    """Determine user's subscription tier: 'pro' or 'free'."""
    if has_active_pro_override(user):
        return "pro"

    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
    )
    active_sub = result.scalars().first()
    return "pro" if active_sub else "free"
