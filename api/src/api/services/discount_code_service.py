"""Discount code helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import DiscountCode

CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,31}$")


def normalize_discount_code(raw: str) -> str:
    """Normalize and validate a user-facing discount code."""
    code = raw.strip().upper()
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError(
            "Code must be 3-32 chars and only use letters, numbers, '-' or '_'"
        )
    return code


def is_discount_code_usable(code: DiscountCode, now: datetime | None = None) -> bool:
    """Return True when code is active and inside its validity window."""
    current = now or datetime.now(UTC)
    if not code.is_active:
        return False
    if code.starts_at and code.starts_at > current:
        return False
    if code.expires_at and code.expires_at <= current:
        return False
    return True


async def resolve_usable_discount_code(
    db: AsyncSession,
    raw_code: str,
) -> DiscountCode | None:
    """Look up a valid active discount code."""
    try:
        code = normalize_discount_code(raw_code)
    except ValueError:
        return None

    result = await db.execute(select(DiscountCode).where(DiscountCode.code == code))
    discount = result.scalars().first()
    if not discount:
        return None
    if not is_discount_code_usable(discount):
        return None
    return discount
