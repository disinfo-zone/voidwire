"""Pydantic schemas for readings."""

from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field


class StandardReading(BaseModel):
    """Standard reading output (~400-600 words)."""
    title: str
    body: str
    word_count: int = 0


class ExtendedSection(BaseModel):
    """A section in the extended reading."""
    heading: str | None = None
    body: str


class ExtendedReading(BaseModel):
    """Extended reading output (~1200-1800 words)."""
    title: str
    subtitle: str | None = None
    sections: list[ExtendedSection]
    word_count: int = 0


class TransitAnnotation(BaseModel):
    """Annotation for a transit in the visualization."""
    aspect: str
    gloss: str
    cultural_resonance: str | None = None
    temporal_arc: str | None = None


class InterpretivePlan(BaseModel):
    """Pass A output - structured interpretive outline."""
    title: str
    opening_strategy: str
    closing_strategy: str
    wild_card_integration: str | None = None
    aspect_readings: list[dict] = Field(default_factory=list)
    tone_notes: dict | None = None


class SynthesisOutput(BaseModel):
    """Complete Pass B output."""
    standard_reading: StandardReading
    extended_reading: ExtendedReading
    transit_annotations: list[TransitAnnotation] = Field(default_factory=list)


class PublicReading(BaseModel):
    """Reading as served by the public API."""
    date_context: date
    title: str
    body: str
    word_count: int = 0
    published_at: datetime | None = None
    has_extended: bool = False
    extended: ExtendedReading | None = None
    annotations: list[TransitAnnotation] | None = None
