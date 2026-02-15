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


class NatalChart(BaseModel):
    """Complete natal chart data."""

    positions: list[NatalPosition]
    angles: list[NatalAngle]
    house_cusps: list[float] = Field(default_factory=list)
    house_signs: list[str] = Field(default_factory=list)
    house_system: str = "placidus"
    aspects: list[NatalAspect] = Field(default_factory=list)
