"""Tests for natal chart calculations."""

from __future__ import annotations

from datetime import date, time

import ephemeris.natal as natal


def test_calculate_natal_chart_includes_lilith_and_metadata():
    chart = natal.calculate_natal_chart(
        birth_date=date(1992, 11, 25),
        birth_time=time(14, 42),
        birth_latitude=33.0393,
        birth_longitude=-85.0319,
        birth_timezone="America/New_York",
        house_system="placidus",
    )

    bodies = {str(p.get("body", "")).lower() for p in chart.get("positions", [])}
    assert "lilith" in bodies
    assert "part_of_fortune" in bodies

    metadata = chart.get("calculation_metadata") or {}
    assert metadata.get("zodiac") == "tropical"
    assert metadata.get("node_mode") == "true"
    assert metadata.get("lilith_mode") == "mean_apogee"
    assert isinstance(metadata.get("position_sources"), dict)
    assert natal.chart_has_required_points(chart) is True


def test_chart_has_required_points_allows_unavailable_lilith():
    chart = {
        "positions": [{"body": "part_of_fortune"}],
        "calculation_metadata": {
            "position_sources": {"sun": "swisseph"},
            "unavailable_bodies": ["lilith"],
        },
    }
    assert natal.chart_has_required_points(chart) is True


def test_chart_has_required_points_rejects_missing_metadata():
    chart = {
        "positions": [{"body": "lilith"}, {"body": "part_of_fortune"}],
    }
    assert natal.chart_has_required_points(chart) is False


def test_calculate_position_returns_unavailable_when_ephemeris_fails(monkeypatch):
    class FakeSwe:
        FLG_SWIEPH = 1
        FLG_SPEED = 2
        FLG_MOSEPH = 4

        def calc_ut(self, jd: float, body_id: int, flags: int):
            raise RuntimeError("missing ephemeris file")

    monkeypatch.setattr(natal, "_HAS_SWISSEPH", True)
    monkeypatch.setattr(natal, "swe", FakeSwe())

    position, source, warning = natal._calculate_position("chiron", 2460000.5)
    assert position is None
    assert source == "unavailable"
    assert warning and "unavailable" in warning
