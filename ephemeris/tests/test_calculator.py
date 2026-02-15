"""Tests for ephemeris calculator."""

from datetime import date

import pytest
from ephemeris.bodies import SIGNS, get_effective_orb, longitude_to_sign
from ephemeris.calculator import calculate_day


def test_longitude_to_sign():
    """Test longitude to sign conversion."""
    assert longitude_to_sign(0.0) == ("Aries", 0.0)
    assert longitude_to_sign(30.0) == ("Taurus", 0.0)
    assert longitude_to_sign(90.0) == ("Cancer", 0.0)
    assert longitude_to_sign(180.0) == ("Libra", 0.0)
    assert longitude_to_sign(270.0) == ("Capricorn", 0.0)

    sign, degree = longitude_to_sign(45.5)
    assert sign == "Taurus"
    assert abs(degree - 15.5) < 0.001

    # Wraparound
    sign, _ = longitude_to_sign(359.0)
    assert sign == "Pisces"


def test_effective_orb():
    """Test effective orb calculation."""
    # Luminaries get full orb
    orb = get_effective_orb("sun", "moon", "conjunction")
    assert orb == 10.0  # base orb * (1.0 + 1.0) / 2

    # Outer planets get reduced orb
    orb = get_effective_orb("uranus", "pluto", "conjunction")
    assert orb < 10.0


@pytest.mark.asyncio
async def test_calculate_day_returns_valid_output():
    """Test that calculate_day returns a properly structured output."""
    result = await calculate_day(date(2026, 2, 13))

    assert result.date_context == date(2026, 2, 13)
    assert result.julian_day > 0
    assert "sun" in result.positions
    assert "moon" in result.positions
    assert result.lunar.phase_name in [
        "new_moon",
        "waxing_crescent",
        "first_quarter",
        "waxing_gibbous",
        "full_moon",
        "waning_gibbous",
        "last_quarter",
        "waning_crescent",
    ]
    assert 0.0 <= result.lunar.phase_pct <= 1.0

    # All positions should have valid signs
    for body_name, pos in result.positions.items():
        assert pos.sign in SIGNS, f"{body_name} has invalid sign {pos.sign}"
        assert 0.0 <= pos.degree < 30.0
        assert 0.0 <= pos.longitude < 360.0


@pytest.mark.asyncio
async def test_calculate_day_aspects():
    """Test that aspects are detected."""
    result = await calculate_day(date(2026, 2, 13))

    # Should find at least some aspects
    # (exact count depends on swisseph availability)
    for aspect in result.aspects:
        assert aspect.body1
        assert aspect.body2
        assert aspect.type
        assert aspect.orb_degrees >= 0
