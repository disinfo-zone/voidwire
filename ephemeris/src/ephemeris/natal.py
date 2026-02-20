"""Natal chart calculator - birth chart positions, houses, and aspects."""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import UTC, date, datetime, time
from typing import Any
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

    ephe_path = str(os.getenv("SWISSEPH_EPHE_PATH", "")).strip()
    swe.set_ephe_path(ephe_path if ephe_path else None)
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

ZODIAC_MODE = "tropical"
NODE_MODE = "true"
LILITH_MODE = "mean_apogee"


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


def _placeholder_position(body_name: str, jd: float) -> tuple[float, float]:
    """Deterministic fallback position used only when Swiss Ephemeris is unavailable."""
    h = int(hashlib.sha256(f"{body_name}{jd}".encode()).hexdigest()[:8], 16)
    longitude = (h % 36000) / 100.0
    speed = 1.0
    return longitude, speed


def _calculate_position(body_name: str, jd: float) -> tuple[dict[str, Any] | None, str, str | None]:
    """Calculate position for a single body.

    Returns (position, source, warning). Position can be None when unavailable.
    """
    body_id = BODY_IDS[body_name]

    if _HAS_SWISSEPH:
        try:
            result, _ = swe.calc_ut(jd, body_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
            longitude = result[0]
            speed = result[3]
            source = "swisseph"
        except Exception:
            try:
                result, _ = swe.calc_ut(jd, body_id, swe.FLG_MOSEPH | swe.FLG_SPEED)
                longitude = result[0]
                speed = result[3]
                source = "moshier"
            except Exception as exc:
                return None, "unavailable", f"{body_name} unavailable: {exc}"
    else:
        longitude, speed = _placeholder_position(body_name, jd)
        source = "placeholder"

    sign, degree = longitude_to_sign(longitude)
    return (
        {
            "body": body_name,
            "sign": sign,
            "degree": round(degree, 2),
            "longitude": round(longitude, 2),
            "speed_deg_day": round(speed, 4),
            "retrograde": speed < 0,
        },
        source,
        None,
    )


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


def _normalized_bodies(chart: dict[str, Any]) -> set[str]:
    bodies: set[str] = set()
    positions = chart.get("positions")
    if not isinstance(positions, list):
        return bodies
    for entry in positions:
        if not isinstance(entry, dict):
            continue
        body = str(entry.get("body", "")).strip().lower()
        if body:
            bodies.add(body)
    return bodies


def chart_has_required_points(chart: object) -> bool:
    """Validate a cached natal chart has required computed points/metadata."""
    if not isinstance(chart, dict):
        return False

    bodies = _normalized_bodies(chart)
    if "part_of_fortune" not in bodies:
        return False

    metadata = chart.get("calculation_metadata")
    if not isinstance(metadata, dict):
        return False

    unavailable = {
        str(body).strip().lower()
        for body in (metadata.get("unavailable_bodies") or [])
        if str(body).strip()
    }
    if "lilith" not in bodies and "lilith" not in unavailable:
        return False

    if not isinstance(metadata.get("position_sources"), dict):
        return False

    return True


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
    house_cusps, house_signs, house_system, aspects, calculation_metadata.
    """
    # Build birth datetime
    bt = birth_time or time(12, 0, 0)  # Noon if unknown
    warnings: list[str] = []
    try:
        tz = ZoneInfo(birth_timezone)
        timezone_used = birth_timezone
    except Exception:
        tz = UTC
        timezone_used = "UTC"
        warnings.append(f"invalid timezone '{birth_timezone}', fallback to UTC")

    birth_dt_local = datetime.combine(birth_date, bt, tzinfo=tz)
    birth_dt_utc = birth_dt_local.astimezone(UTC)
    jd = _datetime_to_jd(birth_dt_local)

    # Calculate house cusps and angles
    cusps: list[float] = []
    ascendant = 0.0
    midheaven = 0.0
    house_signs: list[str] = []

    requested_house_system = str(house_system or "placidus").strip().lower() or "placidus"
    hsys = HOUSE_SYSTEMS.get(requested_house_system, b"P")
    resolved_house_system = requested_house_system if requested_house_system in HOUSE_SYSTEMS else "placidus"
    if requested_house_system not in HOUSE_SYSTEMS:
        warnings.append(f"unknown house system '{house_system}', fallback to placidus")

    if _HAS_SWISSEPH:
        try:
            cusp_result, angle_result = swe.houses_ex(jd, birth_latitude, birth_longitude, hsys)
            cusps = list(cusp_result)
            ascendant = angle_result[0]
            midheaven = angle_result[1]
        except Exception as exc:
            warnings.append(f"house calculation failed, fallback equal houses: {exc}")
            cusps = [(i * 30.0) for i in range(12)]
            ascendant = cusps[0]
            midheaven = cusps[9]
    else:
        warnings.append("pyswisseph unavailable, using placeholder houses")
        cusps = [(i * 30.0) for i in range(12)]
        ascendant = cusps[0]
        midheaven = cusps[9]

    for cusp in cusps:
        sign, _ = longitude_to_sign(cusp)
        house_signs.append(sign)

    # Calculate all body positions
    positions_raw: dict[str, dict] = {}
    positions_list: list[dict] = []
    position_sources: dict[str, str] = {}
    unavailable_bodies: list[str] = []

    for body_name in ALL_BODIES:
        pos, source, warning = _calculate_position(body_name, jd)
        position_sources[body_name] = source
        if warning:
            warnings.append(warning)
        if pos is None:
            unavailable_bodies.append(body_name)
            continue
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

    # Part of Fortune: (Ascendant + Moon - Sun) % 360
    sun_pos = positions_raw.get("sun")
    moon_pos = positions_raw.get("moon")
    if sun_pos and moon_pos:
        pof_longitude = (ascendant + moon_pos["longitude"] - sun_pos["longitude"]) % 360
        pof_sign, pof_degree = longitude_to_sign(pof_longitude)
        positions_list.append(
            {
                "body": "part_of_fortune",
                "sign": pof_sign,
                "degree": round(pof_degree, 2),
                "longitude": round(pof_longitude, 2),
                "speed_deg_day": 0.0,
                "retrograde": False,
                "house": _find_house(pof_longitude, cusps) if birth_time else None,
            }
        )
    else:
        unavailable_bodies.append("part_of_fortune")
        warnings.append("part_of_fortune unavailable: requires both Sun and Moon positions")

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

    calculation_metadata = {
        "ephemeris_engine": "swisseph" if _HAS_SWISSEPH else "placeholder",
        "zodiac": ZODIAC_MODE,
        "node_mode": NODE_MODE,
        "lilith_mode": LILITH_MODE,
        "house_system_requested": requested_house_system,
        "house_system_applied": resolved_house_system,
        "house_system_code": hsys.decode("ascii"),
        "birth_datetime_local": birth_dt_local.isoformat(),
        "birth_datetime_utc": birth_dt_utc.isoformat(),
        "timezone": timezone_used,
        "time_known": birth_time is not None,
        "birth_coordinates": {
            "latitude": round(float(birth_latitude), 6),
            "longitude": round(float(birth_longitude), 6),
        },
        "julian_day_ut": round(float(jd), 8),
        "position_sources": position_sources,
        "unavailable_bodies": sorted(set(unavailable_bodies)),
        "warnings": warnings,
    }

    return {
        "positions": positions_list,
        "angles": angles,
        "house_cusps": [round(c, 2) for c in cusps],
        "house_signs": house_signs,
        "house_system": resolved_house_system,
        "aspects": aspects,
        "calculation_metadata": calculation_metadata,
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
