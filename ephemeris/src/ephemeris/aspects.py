"""Aspect detection and orb calculations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from ephemeris.bodies import (
    ASPECTS,
    ASPECT_BODIES,
    aspect_significance,
    get_effective_orb,
)

logger = logging.getLogger(__name__)


def angular_distance(lon1: float, lon2: float) -> float:
    """Calculate the shortest angular distance between two longitudes."""
    diff = abs(lon1 - lon2) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


def find_aspects(
    positions: dict[str, dict],
    calc_position_at: object | None = None,
    base_dt: datetime | None = None,
) -> list[dict]:
    """Find all active aspects between bodies.

    Args:
        positions: Dict of body name -> {longitude, speed_deg_day, ...}
        calc_position_at: Optional callable(body, julian_day) -> longitude
                         for perfection time calculation
        base_dt: Base datetime for perfection calculations

    Returns:
        List of aspect dicts with body1, body2, type, orb_degrees, applying, etc.
    """
    aspects_found = []
    bodies = [b for b in ASPECT_BODIES if b in positions]

    for i, body1 in enumerate(bodies):
        for body2 in bodies[i + 1:]:
            lon1 = positions[body1]["longitude"]
            lon2 = positions[body2]["longitude"]

            for aspect_name, aspect_angle in ASPECTS.items():
                orb_limit = get_effective_orb(body1, body2, aspect_name)

                # Check if aspect is within orb
                dist = angular_distance(lon1, lon2)
                orb = abs(dist - aspect_angle)

                if orb <= orb_limit:
                    # Determine applying/separating
                    speed1 = positions[body1].get("speed_deg_day", 0.0)
                    speed2 = positions[body2].get("speed_deg_day", 0.0)
                    applying = _is_applying(lon1, lon2, speed1, speed2, aspect_angle)

                    # Estimate perfection time
                    perfects_at = None
                    if applying and base_dt and orb > 0.01:
                        perfects_at = _estimate_perfection(
                            lon1, lon2, speed1, speed2, aspect_angle, base_dt
                        )

                    aspects_found.append({
                        "body1": body1,
                        "body2": body2,
                        "type": aspect_name,
                        "orb_degrees": round(orb, 4),
                        "applying": applying,
                        "perfects_at": perfects_at,
                        "entered_orb_at": None,  # TODO: binary search for orb entry
                        "significance": aspect_significance(aspect_name),
                        "core_meaning": "",
                        "domain_affinities": [],
                    })

    # Sort by significance then orb
    sig_order = {"major": 0, "moderate": 1, "minor": 2}
    aspects_found.sort(key=lambda a: (sig_order.get(a["significance"], 3), a["orb_degrees"]))

    return aspects_found


def _is_applying(
    lon1: float, lon2: float, speed1: float, speed2: float, aspect_angle: float
) -> bool:
    """Determine if an aspect is applying (getting tighter) or separating."""
    # Calculate how the angular distance is changing
    # If the aspect angle is being approached, it's applying
    dist_now = angular_distance(lon1, lon2)

    # Project positions forward slightly
    lon1_future = (lon1 + speed1 * 0.1) % 360.0
    lon2_future = (lon2 + speed2 * 0.1) % 360.0
    dist_future = angular_distance(lon1_future, lon2_future)

    orb_now = abs(dist_now - aspect_angle)
    orb_future = abs(dist_future - aspect_angle)

    return orb_future < orb_now


def _estimate_perfection(
    lon1: float, lon2: float, speed1: float, speed2: float,
    aspect_angle: float, base_dt: datetime,
) -> datetime | None:
    """Estimate when an applying aspect will perfect."""
    dist = angular_distance(lon1, lon2)
    orb = abs(dist - aspect_angle)

    # Relative speed of closure
    # This is a simplification; real calculation needs direction
    relative_speed = abs(speed1 - speed2)
    if relative_speed < 0.001:
        return None  # Too slow to estimate meaningfully

    days_to_perfect = orb / relative_speed
    if days_to_perfect > 30:
        return None  # Too far out to be meaningful

    return base_dt + timedelta(days=days_to_perfect)
