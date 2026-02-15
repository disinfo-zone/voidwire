"""Ephemeris calculation stage."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def run_ephemeris_stage(date_context: date, session: AsyncSession) -> dict[str, Any]:
    from ephemeris.calculator import calculate_day

    result = await calculate_day(date_context, db_session=session)
    return result.model_dump(mode="json")
