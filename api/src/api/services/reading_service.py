"""Reading service."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import Reading


async def get_published_reading(date_context: date, session: AsyncSession) -> Reading | None:
    result = await session.execute(
        select(Reading).where(Reading.date_context == date_context, Reading.status == "published")
    )
    return result.scalars().first()
