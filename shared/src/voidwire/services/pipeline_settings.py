"""Pipeline settings service -- typed Pydantic models backed by site_settings table."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voidwire.models.site_setting import SiteSetting

logger = logging.getLogger(__name__)


class SelectionSettings(BaseModel):
    n_select: int = 9
    n_wild: int = 1
    diversity_bonus: float = 1.5
    intensity_scores: dict[str, float] = Field(
        default={"major": 3.0, "moderate": 2.0, "minor": 1.0}
    )
    wild_card_excluded_domains: list[str] = Field(
        default=["anomalous", "health"]
    )
    quality_floor: float = 0.5
    min_text_length: int = 20


class ThreadSettings(BaseModel):
    match_threshold: float = 0.75
    summary_update_threshold: float = 0.92
    centroid_decay: float = 0.8
    deactivation_days: int = 7
    domain_bonus: float = 0.1
    reactivation_multiplier: int = 3


class SynthesisSettings(BaseModel):
    plan_retries: int = 2
    prose_retries: int = 3
    plan_temp_start: float = 0.7
    plan_temp_step: float = 0.15
    prose_temp_start: float = 0.7
    prose_temp_step: float = 0.1
    prose_temp_min: float = 0.5
    fallback_temp: float = 0.6
    thread_display_limit: int = 10
    signal_display_limit: int = Field(default=12, ge=1, le=40)
    standard_word_range: list[int] = Field(default=[400, 600])
    extended_word_range: list[int] = Field(default=[1200, 1800])
    max_stage_seconds: int = 600
    banned_phrases: list[str] = Field(
        default=[
            "buckle up", "wild ride", "cosmic", "universe has plans",
            "energy", "vibe",
        ]
    )


class IngestionSettings(BaseModel):
    max_per_domain: int = 15
    max_total: int = 80
    fulltext_timeout: float = 5.0
    rss_timeout: float = 15.0


class DistillationSettings(BaseModel):
    content_truncation: int = 500
    target_signals_min: int = 15
    target_signals_max: int = 20


class PipelineSettings(BaseModel):
    selection: SelectionSettings = Field(default_factory=SelectionSettings)
    threads: ThreadSettings = Field(default_factory=ThreadSettings)
    synthesis: SynthesisSettings = Field(default_factory=SynthesisSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    distillation: DistillationSettings = Field(default_factory=DistillationSettings)


async def load_pipeline_settings(session: AsyncSession) -> PipelineSettings:
    """Load pipeline settings from site_settings table, merged with defaults.

    Keys use dotted paths like ``pipeline.selection.n_select``.
    """
    result = await session.execute(
        select(SiteSetting).where(SiteSetting.category == "pipeline")
    )
    rows = result.scalars().all()

    overrides: dict[str, Any] = {}
    for row in rows:
        # Keys stored as "pipeline.selection.n_select" -> nested dict
        key = row.key
        if key.startswith("pipeline."):
            key = key[len("pipeline."):]
        parts = key.split(".")
        if len(parts) == 2:
            group, field = parts
            overrides.setdefault(group, {})[field] = row.value
        elif len(parts) == 1:
            # Top-level pipeline setting
            overrides[parts[0]] = row.value

    defaults = PipelineSettings()
    merged = defaults.model_dump()
    for group, fields in overrides.items():
        if group in merged and isinstance(fields, dict):
            merged[group].update(fields)

    return PipelineSettings(**merged)


def pipeline_settings_schema() -> dict[str, Any]:
    """Return the full JSON Schema for PipelineSettings with defaults."""
    return PipelineSettings.model_json_schema()
