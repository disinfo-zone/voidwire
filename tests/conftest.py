"""Integration test configuration."""

import pytest


@pytest.fixture
def sample_ephemeris():
    """Sample ephemeris data for testing."""
    return {
        "date_context": "2026-02-13",
        "generated_at": "2026-02-13T05:01:12Z",
        "julian_day": 2461421.5,
        "positions": {
            "sun": {"sign": "Aquarius", "degree": 24.73, "longitude": 324.73, "speed_deg_day": 1.01, "retrograde": False},
            "moon": {"sign": "Scorpio", "degree": 18.41, "longitude": 228.41, "speed_deg_day": 13.2, "retrograde": False},
        },
        "lunar": {
            "phase_name": "waning_gibbous",
            "phase_pct": 0.72,
            "void_of_course": False,
        },
        "aspects": [],
        "stations_and_ingresses": [],
        "forward_ephemeris": [],
        "recent_titles": [],
    }


@pytest.fixture
def sample_signals():
    """Sample distilled signals for testing."""
    return [
        {
            "id": "sig_20260213_001",
            "summary": "Major infrastructure strain as transport systems face cascading failures",
            "domain": "economy",
            "intensity": "major",
            "directionality": "escalating",
            "entities": ["infrastructure authority", "transport network"],
            "source_refs": ["[1]", "[3]"],
        },
        {
            "id": "sig_20260213_002",
            "summary": "Diplomatic channels reopen after prolonged silence between regional powers",
            "domain": "diplomacy",
            "intensity": "moderate",
            "directionality": "de-escalating",
            "entities": ["regional powers"],
            "source_refs": ["[2]"],
        },
    ]
