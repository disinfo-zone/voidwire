"""Pydantic schemas for cultural signals."""

from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field


class RawArticle(BaseModel):
    """A raw article from news ingestion."""
    source_id: str
    title: str
    summary: str
    full_text: str | None = None
    url: str
    published_at: str | None = None
    domain: str
    weight: float = 0.5


class DistilledSignal(BaseModel):
    """A distilled cultural signal from LLM processing."""
    summary: str
    domain: str
    intensity: str
    directionality: str
    entities: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class SignalWithEmbedding(BaseModel):
    """A signal with its embedding vector."""
    id: str
    summary: str
    domain: str
    intensity: str
    directionality: str
    entities: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    was_selected: bool = False
    was_wild_card: bool = False
    selection_weight: float | None = None
