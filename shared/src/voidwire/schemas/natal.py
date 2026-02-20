"""Pydantic schemas for natal chart data."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NatalPosition(BaseModel):
    """Position of a body in a natal chart."""

    body: str
    sign: str
    degree: float
    longitude: float
    speed_deg_day: float
    retrograde: bool
    house: int | None = None


class NatalAngle(BaseModel):
    """An angular point (ASC, MC, etc.)."""

    name: str
    sign: str
    degree: float
    longitude: float


class NatalAspect(BaseModel):
    """An aspect in the natal chart."""

    body1: str
    body2: str
    type: str
    orb_degrees: float
    applying: bool
    significance: str = "moderate"


class NatalCoordinates(BaseModel):
    latitude: float
    longitude: float


class NatalCalculationMetadata(BaseModel):
    ephemeris_engine: str = "swisseph"
    zodiac: str = "tropical"
    node_mode: str = "true"
    lilith_mode: str = "mean_apogee"
    house_system_requested: str = "placidus"
    house_system_applied: str = "placidus"
    house_system_code: str = "P"
    birth_datetime_local: str
    birth_datetime_utc: str
    timezone: str
    time_known: bool = False
    birth_coordinates: NatalCoordinates
    julian_day_ut: float
    position_sources: dict[str, str] = Field(default_factory=dict)
    unavailable_bodies: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class NatalChart(BaseModel):
    """Complete natal chart data."""

    positions: list[NatalPosition]
    angles: list[NatalAngle]
    house_cusps: list[float] = Field(default_factory=list)
    house_signs: list[str] = Field(default_factory=list)
    house_system: str = "placidus"
    aspects: list[NatalAspect] = Field(default_factory=list)
    calculation_metadata: NatalCalculationMetadata | None = None
