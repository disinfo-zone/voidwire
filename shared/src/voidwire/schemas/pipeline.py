"""Pydantic schemas for pipeline operations."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class PipelineStatus(str, Enum):
    """Pipeline run status."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RegenerationMode(str, Enum):
    """Regeneration mode for pipeline reruns."""

    PROSE_ONLY = "prose_only"
    RESELECT = "reselect"
    FULL_RERUN = "full_rerun"


class PipelineRunSummary(BaseModel):
    """Summary of a pipeline run."""

    id: str
    date_context: date
    run_number: int
    status: PipelineStatus
    started_at: datetime
    ended_at: datetime | None = None
    regeneration_mode: str | None = None
    error_detail: str | None = None


class PipelineTriggerRequest(BaseModel):
    """Request to trigger a pipeline run."""

    date_context: date | None = None
    regeneration_mode: RegenerationMode | None = None
    parent_run_id: str | None = None


class StageResult(BaseModel):
    """Result from a single pipeline stage."""

    stage_name: str
    success: bool
    duration_seconds: float = 0.0
    artifacts: dict = Field(default_factory=dict)
    error: str | None = None
