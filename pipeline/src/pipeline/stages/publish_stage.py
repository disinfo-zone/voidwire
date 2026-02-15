"""Publish stage."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import PipelineRun, Reading, SiteSetting

logger = logging.getLogger(__name__)


def _trigger_source(run: PipelineRun | None) -> str:
    if run is None:
        return "scheduler"
    artifacts = run.reused_artifacts if isinstance(run.reused_artifacts, dict) else {}
    source = str(artifacts.get("trigger_source", "scheduler")).strip().lower()
    return source or "scheduler"


async def run_publish_stage(
    reading: Reading,
    session: AsyncSession,
    run: PipelineRun | None = None,
) -> None:
    result = await session.execute(
        select(SiteSetting).where(SiteSetting.key == "pipeline.auto_publish")
    )
    setting = result.scalars().first()
    auto_publish = False
    if setting and setting.value:
        auto_publish = (
            setting.value.get("enabled", False)
            if isinstance(setting.value, dict)
            else bool(setting.value)
        )

    source = _trigger_source(run)
    should_auto_publish = auto_publish and source == "scheduler"
    if not should_auto_publish:
        reading.status = "pending"
        return

    now = datetime.now(UTC)
    existing = await session.execute(
        select(Reading).where(
            Reading.date_context == reading.date_context,
            Reading.status == "published",
            Reading.id != reading.id,
        )
    )
    for published in existing.scalars().all():
        published.status = "archived"
        published.updated_at = now

    reading.status = "published"
    reading.updated_at = now
    reading.published_at = now
    reading.published_standard = reading.generated_standard
    reading.published_extended = reading.generated_extended
    reading.published_annotations = reading.generated_annotations
