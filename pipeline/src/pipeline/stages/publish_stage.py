"""Publish stage."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import Reading, SiteSetting

logger = logging.getLogger(__name__)

async def run_publish_stage(reading: Reading, session: AsyncSession) -> None:
    result = await session.execute(select(SiteSetting).where(SiteSetting.key == "pipeline.auto_publish"))
    setting = result.scalars().first()
    auto_publish = False
    if setting and setting.value:
        auto_publish = setting.value.get("enabled", False) if isinstance(setting.value, dict) else bool(setting.value)
    if auto_publish:
        reading.status = "published"
        reading.published_at = datetime.now(timezone.utc)
        reading.published_standard = reading.generated_standard
        reading.published_extended = reading.generated_extended
        reading.published_annotations = reading.generated_annotations
