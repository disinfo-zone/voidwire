"""Tests for pipeline scheduler utilities."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pipeline.__main__ import _next_run, _parse_daily_schedule


def test_parse_daily_schedule():
    hour, minute = _parse_daily_schedule("0 5 * * *")
    assert (hour, minute) == (5, 0)


def test_parse_daily_schedule_rejects_non_daily():
    with pytest.raises(ValueError):
        _parse_daily_schedule("*/5 * * * *")


def test_next_run_rolls_to_next_day_when_past_target():
    tz = ZoneInfo("UTC")
    now = datetime(2026, 2, 14, 6, 0, tzinfo=tz)
    target = _next_run(now, 5, 0)
    assert target.isoformat() == "2026-02-15T05:00:00+00:00"
