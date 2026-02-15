"""Pydantic schemas for ephemeris data."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PlanetPosition(BaseModel):
    """Position of a celestial body."""

    sign: str
    degree: float
    longitude: float
    speed_deg_day: float
    retrograde: bool


class LunarData(BaseModel):
    """Lunar phase and void-of-course data."""

    phase_name: str
    phase_pct: float = Field(ge=0.0, le=1.0)
    void_of_course: bool
    void_of_course_starts: datetime | None = None
    next_sign_ingress: dict | None = None


class Aspect(BaseModel):
    """An aspect between two bodies."""

    body1: str
    body2: str
    type: str
    orb_degrees: float
    applying: bool
    perfects_at: datetime | None = None
    entered_orb_at: datetime | None = None
    significance: str = "moderate"
    core_meaning: str = ""
    domain_affinities: list[str] = Field(default_factory=list)


class StationOrIngress(BaseModel):
    """A station or sign ingress event."""

    type: str  # 'ingress', 'station_retrograde', 'station_direct'
    body: str
    sign: str | None = None
    at: datetime
    core_meaning: str = ""


class ForwardEvent(BaseModel):
    """A forward-looking ephemeris event."""

    at: datetime
    event: str
    significance: str = "moderate"
    core_meaning: str | None = None


class EphemerisOutput(BaseModel):
    """Complete ephemeris output for a given day."""

    date_context: date
    generated_at: datetime
    julian_day: float

    positions: dict[str, PlanetPosition]
    lunar: LunarData
    aspects: list[Aspect]
    stations_and_ingresses: list[StationOrIngress] = Field(default_factory=list)
    forward_ephemeris: list[ForwardEvent] = Field(default_factory=list)
    recent_titles: list[str] = Field(default_factory=list)
