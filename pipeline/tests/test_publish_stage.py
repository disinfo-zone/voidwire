"""Tests for publish stage source-aware behavior."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pipeline.stages.publish_stage import run_publish_stage


@dataclass
class _ReadingStub:
    id: uuid.UUID
    date_context: date
    status: str = "pending"
    generated_standard: dict | None = None
    generated_extended: dict | None = None
    generated_annotations: list | None = None
    published_standard: dict | None = None
    published_extended: dict | None = None
    published_annotations: list | None = None
    published_at: object | None = None
    updated_at: object | None = None


def _result_with_setting(enabled: bool) -> MagicMock:
    setting = SimpleNamespace(value={"enabled": enabled})
    result = MagicMock()
    result.scalars.return_value.first.return_value = setting
    return result


@pytest.mark.asyncio
async def test_manual_run_stays_pending_even_when_auto_publish_enabled():
    reading = _ReadingStub(
        id=uuid.uuid4(),
        date_context=date(2026, 2, 14),
        generated_standard={"title": "T", "body": "B"},
        generated_extended={"title": "", "subtitle": "", "sections": [], "word_count": 0},
        generated_annotations=[],
    )
    session = AsyncMock()
    session.execute.return_value = _result_with_setting(enabled=True)
    run = SimpleNamespace(reused_artifacts={"trigger_source": "manual"})

    await run_publish_stage(reading, session, run)

    assert reading.status == "pending"
    assert reading.published_standard is None
    assert reading.published_extended is None
    assert reading.published_annotations is None
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_scheduler_run_auto_publishes_and_archives_previous_publish():
    reading = _ReadingStub(
        id=uuid.uuid4(),
        date_context=date(2026, 2, 14),
        generated_standard={"title": "Latest", "body": "Body"},
        generated_extended={
            "title": "Expanded",
            "subtitle": "Sub",
            "sections": [{"heading": "H", "body": "B"}],
            "word_count": 1200,
        },
        generated_annotations=[{"aspect": "Sun trine Moon"}],
    )
    previous = _ReadingStub(
        id=uuid.uuid4(),
        date_context=date(2026, 2, 14),
        status="published",
    )

    setting_result = _result_with_setting(enabled=True)
    published_result = MagicMock()
    published_result.scalars.return_value.all.return_value = [previous]

    session = AsyncMock()
    session.execute.side_effect = [setting_result, published_result]
    run = SimpleNamespace(reused_artifacts={"trigger_source": "scheduler"})

    await run_publish_stage(reading, session, run)

    assert previous.status == "archived"
    assert previous.updated_at is not None
    assert reading.status == "published"
    assert reading.published_at is not None
    assert reading.updated_at is not None
    assert reading.published_standard == reading.generated_standard
    assert reading.published_extended == reading.generated_extended
    assert reading.published_annotations == reading.generated_annotations
    assert session.execute.await_count == 2
