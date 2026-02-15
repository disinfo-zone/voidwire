"""Main ephemeris calculator - calculate_day() entry point."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from voidwire.schemas.ephemeris import (
    Aspect,
    EphemerisOutput,
    ForwardEvent,
    LunarData,
    PlanetPosition,
    StationOrIngress,
)
from ephemeris.bodies import ALL_BODIES, BODY_IDS, SIGNS, longitude_to_sign
from ephemeris.aspects import find_aspects
from ephemeris.lunar import (
    calculate_lunar_phase,
    calculate_next_ingress,
    calculate_void_of_course,
)
from ephemeris.meanings import lookup_meaning

logger = logging.getLogger(__name__)

try:
    import swisseph as swe

    # Use tropical zodiac, geocentric
    swe.set_ephe_path(None)  # Use built-in ephemeris
    _HAS_SWISSEPH = True
except ImportError:
    _HAS_SWISSEPH = False
    logger.warning("pyswisseph not installed, using placeholder calculations")


def _datetime_to_jd(dt: datetime) -> float:
    """Convert datetime to Julian Day number."""
    if _HAS_SWISSEPH:
        utc = dt.astimezone(timezone.utc)
        jd = swe.julday(utc.year, utc.month, utc.day,
                        utc.hour + utc.minute / 60.0 + utc.second / 3600.0)
        return jd
    # Rough Julian Day calculation as fallback
    y = dt.year
    m = dt.month
    d = dt.day + dt.hour / 24.0 + dt.minute / 1440.0
    if m <= 2:
        y -= 1
        m += 12
    A = int(y / 100)
    B = 2 - A + int(A / 4)
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5


def _calculate_position(body_name: str, jd: float) -> dict:
    """Calculate position for a single body at a Julian Day."""
    body_id = BODY_IDS[body_name]

    if _HAS_SWISSEPH:
        # SEFLG_SPEED for speed calculation
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        try:
            result, ret_flags = swe.calc_ut(jd, body_id, flags)
            longitude = result[0]
            speed = result[3]
        except Exception:
            # Fallback to Moshier (no external files needed)
            try:
                flags = swe.FLG_MOSEPH | swe.FLG_SPEED
                result, ret_flags = swe.calc_ut(jd, body_id, flags)
                longitude = result[0]
                speed = result[3]
            except Exception:
                logger.warning("swisseph failed for %s, using placeholder", body_name)
                import hashlib
                h = int(hashlib.sha256(f"{body_name}{jd}".encode()).hexdigest()[:8], 16)
                longitude = (h % 36000) / 100.0
                speed = 1.0 if body_name in ("sun", "moon", "mercury", "venus") else 0.1
    else:
        # Placeholder for when swisseph is not available
        # This produces deterministic but inaccurate positions
        import hashlib
        h = int(hashlib.sha256(f"{body_name}{jd}".encode()).hexdigest()[:8], 16)
        longitude = (h % 36000) / 100.0
        speed = 1.0 if body_name in ("sun", "moon", "mercury", "venus") else 0.1

    sign, degree = longitude_to_sign(longitude)
    retrograde = speed < 0

    return {
        "sign": sign,
        "degree": round(degree, 2),
        "longitude": round(longitude, 2),
        "speed_deg_day": round(speed, 4),
        "retrograde": retrograde,
    }


async def calculate_day(
    target_date: date,
    db_session: object | None = None,
    recent_titles: list[str] | None = None,
) -> EphemerisOutput:
    """Calculate complete ephemeris data for a given date.

    Args:
        target_date: The date to calculate for
        db_session: Optional async DB session for meaning lookup
        recent_titles: Recent reading titles to include

    Returns:
        EphemerisOutput with all positions, aspects, lunar data, etc.
    """
    dt = datetime(target_date.year, target_date.month, target_date.day,
                  12, 0, 0, tzinfo=timezone.utc)  # Noon UTC
    jd = _datetime_to_jd(dt)

    # Calculate all positions
    positions_raw: dict[str, dict] = {}
    for body_name in ALL_BODIES:
        positions_raw[body_name] = _calculate_position(body_name, jd)

    # Convert to Pydantic models
    positions = {
        name: PlanetPosition(**data) for name, data in positions_raw.items()
    }

    # Calculate aspects
    aspects_raw = find_aspects(positions_raw, base_dt=dt)

    # Enrich aspects with meanings
    aspects = []
    for a in aspects_raw:
        meaning = await lookup_meaning(
            a["body1"], a["body2"], a["type"], "aspect", db_session
        )
        aspects.append(Aspect(
            body1=a["body1"],
            body2=a["body2"],
            type=a["type"],
            orb_degrees=a["orb_degrees"],
            applying=a["applying"],
            perfects_at=a.get("perfects_at"),
            entered_orb_at=a.get("entered_orb_at"),
            significance=a["significance"],
            core_meaning=meaning["core_meaning"],
            domain_affinities=meaning["domain_affinities"],
        ))

    # Calculate lunar data
    sun_lon = positions_raw["sun"]["longitude"]
    moon_lon = positions_raw["moon"]["longitude"]
    moon_speed = positions_raw["moon"]["speed_deg_day"]

    phase_name, phase_pct = calculate_lunar_phase(sun_lon, moon_lon)
    void, void_starts = calculate_void_of_course(
        moon_lon, moon_speed, positions_raw, dt
    )
    next_ingress = calculate_next_ingress(moon_lon, moon_speed, dt)

    lunar = LunarData(
        phase_name=phase_name,
        phase_pct=phase_pct,
        void_of_course=void,
        void_of_course_starts=void_starts,
        next_sign_ingress=next_ingress,
    )

    # Detect stations and ingresses (check +-1 day)
    stations_and_ingresses = await _detect_stations_and_ingresses(
        positions_raw, jd, dt, db_session
    )

    # Forward ephemeris (5-day lookahead)
    forward = await _calculate_forward(positions_raw, jd, dt, db_session)

    return EphemerisOutput(
        date_context=target_date,
        generated_at=datetime.now(timezone.utc),
        julian_day=round(jd, 6),
        positions=positions,
        lunar=lunar,
        aspects=aspects,
        stations_and_ingresses=stations_and_ingresses,
        forward_ephemeris=forward,
        recent_titles=recent_titles or [],
    )


async def _detect_stations_and_ingresses(
    positions: dict[str, dict],
    jd: float,
    base_dt: datetime,
    db_session: object | None,
) -> list[StationOrIngress]:
    """Detect retrograde stations and sign ingresses near the target date."""
    events = []

    for body_name in ALL_BODIES:
        if body_name in ("sun", "moon", "north_node"):
            continue  # Sun/Moon don't go retrograde meaningfully

        # Check for station: speed near zero
        speed = positions[body_name]["speed_deg_day"]
        if abs(speed) < 0.01:
            event_type = "station_retrograde" if speed <= 0 else "station_direct"
            meaning = await lookup_meaning(body_name, None, None, "station", db_session)
            events.append(StationOrIngress(
                type=event_type,
                body=body_name,
                sign=positions[body_name]["sign"],
                at=base_dt,
                core_meaning=meaning["core_meaning"],
            ))

        # Check for sign ingress: degree near 0 or 30
        degree = positions[body_name]["degree"]
        if degree < 1.0 and speed > 0:
            meaning = await lookup_meaning(body_name, None, None, "ingress", db_session)
            events.append(StationOrIngress(
                type="ingress",
                body=body_name,
                sign=positions[body_name]["sign"],
                at=base_dt,
                core_meaning=meaning["core_meaning"],
            ))

    return events


async def _calculate_forward(
    positions: dict[str, dict],
    jd: float,
    base_dt: datetime,
    db_session: object | None,
) -> list[ForwardEvent]:
    """Calculate forward-looking ephemeris events (5-day lookahead)."""
    forward = []

    # Check Moon ingresses
    moon_speed = positions["moon"]["speed_deg_day"]
    if moon_speed > 0:
        moon_lon = positions["moon"]["longitude"]
        current_sign, current_degree = longitude_to_sign(moon_lon)

        # Moon changes signs roughly every 2.5 days
        for days_ahead in [1, 2, 3, 4, 5]:
            future_lon = (moon_lon + moon_speed * days_ahead) % 360.0
            future_sign, _ = longitude_to_sign(future_lon)
            prev_lon = (moon_lon + moon_speed * (days_ahead - 0.5)) % 360.0
            prev_sign, _ = longitude_to_sign(prev_lon)

            if future_sign != prev_sign:
                from datetime import timedelta
                event_time = base_dt + timedelta(days=days_ahead)
                forward.append(ForwardEvent(
                    at=event_time,
                    event=f"Moon enters {future_sign}",
                    significance="minor",
                ))

    # Check applying major aspects for perfection
    from ephemeris.aspects import find_aspects
    for aspect in find_aspects(positions, base_dt=base_dt):
        if aspect["applying"] and aspect["perfects_at"] and aspect["significance"] == "major":
            perfects = aspect["perfects_at"]
            if isinstance(perfects, datetime):
                days_out = (perfects - base_dt).total_seconds() / 86400.0
                if 0 < days_out <= 5:
                    forward.append(ForwardEvent(
                        at=perfects,
                        event=f"{aspect['body1'].title()} {aspect['type']} {aspect['body2'].title()} perfects",
                        significance="major",
                    ))

    # Sort by time
    forward.sort(key=lambda e: e.at)
    return forward
