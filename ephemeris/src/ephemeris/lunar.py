"""Lunar phase, void-of-course, and ingress calculations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from ephemeris.bodies import SIGNS, longitude_to_sign

logger = logging.getLogger(__name__)

# Named lunar phases with their synodic percentage ranges
PHASE_NAMES = [
    (0.000, 0.0625, "new_moon"),
    (0.0625, 0.1875, "waxing_crescent"),
    (0.1875, 0.3125, "first_quarter"),
    (0.3125, 0.4375, "waxing_gibbous"),
    (0.4375, 0.5625, "full_moon"),
    (0.5625, 0.6875, "waning_gibbous"),
    (0.6875, 0.8125, "last_quarter"),
    (0.8125, 0.9375, "waning_crescent"),
    (0.9375, 1.000, "new_moon"),
]

# Aspects that end void-of-course (major aspects to planets, not nodes)
VOC_ENDING_ASPECTS = {"conjunction", "sextile", "square", "trine", "opposition"}


def calculate_lunar_phase(sun_longitude: float, moon_longitude: float) -> tuple[str, float]:
    """Calculate lunar phase from Sun and Moon longitudes.

    Returns:
        Tuple of (phase_name, phase_pct) where phase_pct is synodic progress
        0.0 = new moon, 0.5 = full moon, 1.0 = next new moon.
    """
    # Phase angle: Moon's elongation from Sun
    elongation = (moon_longitude - sun_longitude) % 360.0
    phase_pct = elongation / 360.0

    # Determine named phase
    phase_name = "new_moon"
    for low, high, name in PHASE_NAMES:
        if low <= phase_pct < high:
            phase_name = name
            break

    return phase_name, round(phase_pct, 4)


def calculate_void_of_course(
    moon_longitude: float,
    moon_speed: float,
    positions: dict[str, dict],
    base_dt: datetime,
    calc_moon_at: object | None = None,
) -> tuple[bool, datetime | None]:
    """Determine if the Moon is void of course.

    The Moon is void of course when it makes no more major aspects
    to other planets before leaving its current sign.

    This is a simplified calculation that checks current aspects
    and estimates based on speeds.

    Returns:
        Tuple of (is_void, void_starts_at)
    """
    current_sign, current_degree = longitude_to_sign(moon_longitude)
    degrees_left_in_sign = 30.0 - current_degree

    if moon_speed <= 0:
        # Moon barely moves or is calculated incorrectly
        return False, None

    # Hours until Moon leaves current sign
    hours_to_ingress = (degrees_left_in_sign / moon_speed) * 24.0

    # Check if Moon will make any major aspects before leaving sign
    will_aspect = False
    from ephemeris.aspects import angular_distance, ASPECTS

    for body_name, body_data in positions.items():
        if body_name == "moon" or body_name == "north_node":
            continue
        body_lon = body_data["longitude"]

        for aspect_name in VOC_ENDING_ASPECTS:
            aspect_angle = ASPECTS[aspect_name]
            # Check if Moon will cross this aspect angle before leaving sign
            # Simplified: check if the aspect orb is decreasing and will perfect
            dist = angular_distance(moon_longitude, body_lon)
            orb = abs(dist - aspect_angle)
            if orb < 8.0:
                # Close enough to potentially be applying
                # Check future position
                future_moon_lon = (moon_longitude + moon_speed * (hours_to_ingress / 24.0)) % 360
                future_dist = angular_distance(future_moon_lon, body_lon)
                future_orb = abs(future_dist - aspect_angle)
                if future_orb < orb:
                    will_aspect = True
                    break
        if will_aspect:
            break

    is_void = not will_aspect
    void_starts = base_dt if is_void else None

    return is_void, void_starts


def calculate_next_ingress(
    moon_longitude: float,
    moon_speed: float,
    base_dt: datetime,
) -> dict | None:
    """Calculate when the Moon enters its next sign.

    Returns:
        Dict with 'sign' and 'at' keys, or None.
    """
    if moon_speed <= 0:
        return None

    current_sign, current_degree = longitude_to_sign(moon_longitude)
    degrees_left = 30.0 - current_degree
    days_to_ingress = degrees_left / moon_speed

    next_sign_index = (SIGNS.index(current_sign) + 1) % 12
    next_sign = SIGNS[next_sign_index]

    ingress_time = base_dt + timedelta(days=days_to_ingress)

    return {
        "sign": next_sign,
        "at": ingress_time.isoformat(),
    }
