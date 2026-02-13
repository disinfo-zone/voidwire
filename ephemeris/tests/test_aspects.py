"""Tests for aspect detection."""

from ephemeris.aspects import angular_distance, find_aspects, _is_applying


def test_angular_distance():
    """Test angular distance calculation."""
    assert angular_distance(0, 90) == 90.0
    assert angular_distance(90, 0) == 90.0
    assert angular_distance(0, 180) == 180.0
    assert angular_distance(350, 10) == 20.0
    assert angular_distance(10, 350) == 20.0
    assert abs(angular_distance(0, 0) - 0.0) < 0.001


def test_angular_distance_wraparound():
    """Test angular distance handles wraparound correctly."""
    assert abs(angular_distance(355, 5) - 10.0) < 0.001
    assert abs(angular_distance(1, 359) - 2.0) < 0.001


def test_find_aspects_with_known_positions():
    """Test aspect detection with known positions."""
    positions = {
        "sun": {"longitude": 324.0, "speed_deg_day": 1.0},
        "moon": {"longitude": 228.0, "speed_deg_day": 13.0},
        "mars": {"longitude": 112.0, "speed_deg_day": 0.6},
        "saturn": {"longitude": 355.0, "speed_deg_day": 0.05},
    }

    aspects = find_aspects(positions)

    # Should find aspects between these bodies
    assert isinstance(aspects, list)
    for a in aspects:
        assert "body1" in a
        assert "body2" in a
        assert "type" in a
        assert "orb_degrees" in a
        assert a["orb_degrees"] >= 0


def test_is_applying():
    """Test applying/separating detection."""
    # Faster body approaching slower body from behind
    assert _is_applying(100.0, 110.0, 1.0, 0.1, 0.0) is True

    # Bodies moving apart
    assert _is_applying(100.0, 110.0, -1.0, 1.0, 0.0) is False
