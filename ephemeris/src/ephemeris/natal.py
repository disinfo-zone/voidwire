"""Natal chart calculator - birth chart positions, houses, and aspects."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from ephemeris.aspects import angular_distance, find_aspects
from ephemeris.bodies import (
    ALL_BODIES,
    ASPECTS,
    BODY_IDS,
    aspect_significance,
    get_effective_orb,
    longitude_to_sign,
)

logger = logging.getLogger(__name__)

try:
    import swisseph as swe

    swe.set_ephe_path(None)
    _HAS_SWISSEPH = True
except ImportError:
    _HAS_SWISSEPH = False
    logger.warning("pyswisseph not installed, natal chart calculations will use placeholders")


HOUSE_SYSTEMS: dict[str, bytes] = {
    "placidus": b"P",
    "whole_sign": b"W",
    "koch": b"K",
    "equal": b"E",
    "porphyry": b"O",
}


def _datetime_to_jd(dt: datetime) -> float:
    """Convert datetime to Julian Day number."""
    if _HAS_SWISSEPH:
        utc = dt.astimezone(UTC)
        return swe.julday(
            utc.year,
            utc.month,
            utc.day,
            utc.hour + utc.minute / 60.0 + utc.second / 3600.0,
        )
    y = dt.year
    m = dt.month
    d = dt.day + dt.hour / 24.0 + dt.minute / 1440.0
    if m <= 2:
        y -= 1
        m += 12
    a_term = int(y / 100)
    b_term = 2 - a_term + int(a_term / 4)
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b_term - 1524.5


def _calculate_position(body_name: str, jd: float) -> dict:
    """Calculate position for a single body at a Julian Day."""
    body_id = BODY_IDS[body_name]

    if _HAS_SWISSEPH:
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        try:
            result, _ = swe.calc_ut(jd, body_id, flags)
            longitude = result[0]
            speed = result[3]
        except Exception:
            try:
                flags = swe.FLG_MOSEPH | swe.FLG_SPEED
                result, _ = swe.calc_ut(jd, body_id, flags)
                longitude = result[0]
                speed = result[3]
            except Exception:
                import hashlib

                h = int(hashlib.sha256(f"{body_name}{jd}".encode()).hexdigest()[:8], 16)
                longitude = (h % 36000) / 100.0
                speed = 1.0
    else:
        import hashlib

        h = int(hashlib.sha256(f"{body_name}{jd}".encode()).hexdigest()[:8], 16)
        longitude = (h % 36000) / 100.0
        speed = 1.0

    sign, degree = longitude_to_sign(longitude)
    return {
        "body": body_name,
        "sign": sign,
        "degree": round(degree, 2),
        "longitude": round(longitude, 2),
        "speed_deg_day": round(speed, 4),
        "retrograde": speed < 0,
    }


def _find_house(longitude: float, cusps: list[float]) -> int:
    """Determine which house a planet falls in given house cusps."""
    if not cusps or len(cusps) < 12:
        return 1
    for i in range(12):
        cusp_start = cusps[i]
        cusp_end = cusps[(i + 1) % 12]
        if cusp_start <= cusp_end:
            if cusp_start <= longitude < cusp_end:
                return i + 1
        else:
            # Wraps around 0 degrees
            if longitude >= cusp_start or longitude < cusp_end:
                return i + 1
    return 1


def calculate_natal_chart(
    birth_date: date,
    birth_time: time | None,
    birth_latitude: float,
    birth_longitude: float,
    birth_timezone: str,
    house_system: str = "placidus",
) -> dict:
    """Calculate a full natal chart.

    Returns a dict matching the NatalChart schema: positions, angles,
    house_cusps, house_signs, house_system, aspects.
    """
    # Build birth datetime
    bt = birth_time or time(12, 0, 0)  # Noon if unknown
    try:
        tz = ZoneInfo(birth_timezone)
    except Exception:
        tz = UTC
    birth_dt = datetime.combine(birth_date, bt, tzinfo=tz)
    jd = _datetime_to_jd(birth_dt)

    # Calculate house cusps and angles
    cusps: list[float] = []
    ascendant = 0.0
    midheaven = 0.0
    house_signs: list[str] = []

    hsys = HOUSE_SYSTEMS.get(house_system, b"P")

    if _HAS_SWISSEPH:
        try:
            cusp_result, angle_result = swe.houses_ex(jd, birth_latitude, birth_longitude, hsys)
            cusps = list(cusp_result)
            ascendant = angle_result[0]
            midheaven = angle_result[1]
        except Exception:
            logger.warning("House calculation failed, using equal houses from 0")
            cusps = [(i * 30.0) for i in range(12)]
            ascendant = cusps[0]
            midheaven = cusps[9]
    else:
        cusps = [(i * 30.0) for i in range(12)]
        ascendant = cusps[0]
        midheaven = cusps[9]

    for cusp in cusps:
        sign, _ = longitude_to_sign(cusp)
        house_signs.append(sign)

    # Calculate all body positions
    positions_raw: dict[str, dict] = {}
    positions_list: list[dict] = []

    for body_name in ALL_BODIES:
        pos = _calculate_position(body_name, jd)
        pos["house"] = _find_house(pos["longitude"], cusps) if birth_time else None
        positions_raw[body_name] = pos
        positions_list.append(pos)

    # Build angles
    asc_sign, asc_deg = longitude_to_sign(ascendant)
    mc_sign, mc_deg = longitude_to_sign(midheaven)
    angles = [
        {
            "name": "Ascendant",
            "sign": asc_sign,
            "degree": round(asc_deg, 2),
            "longitude": round(ascendant, 2),
        },
        {
            "name": "Midheaven",
            "sign": mc_sign,
            "degree": round(mc_deg, 2),
            "longitude": round(midheaven, 2),
        },
    ]

    # Calculate natal aspects (natal-to-natal)
    # Reuse find_aspects with base_dt=None to skip perfection timing
    aspects_raw = find_aspects(positions_raw, base_dt=None)
    aspects = [
        {
            "body1": a["body1"],
            "body2": a["body2"],
            "type": a["type"],
            "orb_degrees": a["orb_degrees"],
            "applying": a["applying"],
            "significance": a["significance"],
        }
        for a in aspects_raw
    ]

    return {
        "positions": positions_list,
        "angles": angles,
        "house_cusps": [round(c, 2) for c in cusps],
        "house_signs": house_signs,
        "house_system": house_system,
        "aspects": aspects,
    }


def calculate_transit_to_natal_aspects(
    transit_positions: dict[str, dict],
    natal_positions: list[dict],
    orb_factor: float = 0.8,
) -> list[dict]:
    """Find aspects between current transits and natal planet positions.

    Uses tighter orbs (multiplied by orb_factor) for transit-to-natal.
    """
    aspects_found = []
    natal_by_name = {p["body"]: p for p in natal_positions}

    for transit_name, transit_data in transit_positions.items():
        t_lon = transit_data["longitude"]
        transit_data.get("speed_deg_day", 0.0)

        for natal_name, natal_data in natal_by_name.items():
            n_lon = natal_data["longitude"]

            for aspect_name, aspect_angle in ASPECTS.items():
                base_orb = get_effective_orb(transit_name, natal_name, aspect_name)
                orb_limit = base_orb * orb_factor

                dist = angular_distance(t_lon, n_lon)
                orb = abs(dist - aspect_angle)

                if orb <= orb_limit:
                    aspects_found.append(
                        {
                            "transit_body": transit_name,
                            "natal_body": natal_name,
                            "type": aspect_name,
                            "orb_degrees": round(orb, 4),
                            "significance": aspect_significance(aspect_name),
                        }
                    )

    sig_order = {"major": 0, "moderate": 1, "minor": 2}
    aspects_found.sort(key=lambda a: (sig_order.get(a["significance"], 3), a["orb_degrees"]))
    return aspects_found
