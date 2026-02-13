"""Tests for lunar calculations."""

from ephemeris.lunar import calculate_lunar_phase, PHASE_NAMES


def test_new_moon():
    """Test new moon detection (Sun and Moon at same longitude)."""
    phase_name, phase_pct = calculate_lunar_phase(100.0, 100.0)
    assert phase_name == "new_moon"
    assert phase_pct < 0.07


def test_full_moon():
    """Test full moon detection (Sun and Moon opposite)."""
    phase_name, phase_pct = calculate_lunar_phase(100.0, 280.0)
    assert phase_name == "full_moon"
    assert abs(phase_pct - 0.5) < 0.07


def test_first_quarter():
    """Test first quarter detection."""
    phase_name, phase_pct = calculate_lunar_phase(100.0, 190.0)
    assert phase_name == "first_quarter"
    assert abs(phase_pct - 0.25) < 0.07


def test_phase_pct_range():
    """Test that phase_pct is always in [0, 1)."""
    for sun_lon in range(0, 360, 30):
        for moon_lon in range(0, 360, 30):
            _, pct = calculate_lunar_phase(float(sun_lon), float(moon_lon))
            assert 0.0 <= pct < 1.0, f"Phase pct {pct} out of range for sun={sun_lon}, moon={moon_lon}"
