"""Archetypal meaning models - pre-computed aspect meanings and keyword tables."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from voidwire.models.base import Base


class ArchetypalMeaning(Base):
    __tablename__ = "archetypal_meanings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    body1: Mapped[str] = mapped_column(Text, nullable=False)
    body2: Mapped[str | None] = mapped_column(Text)
    aspect_type: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    core_meaning: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    domain_affinities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'generated'")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('aspect','retrograde','ingress','station','lunar_phase')",
            name="ck_meaning_event_type",
        ),
        CheckConstraint("source IN ('generated','curated')", name="ck_meaning_source"),
    )


class PlanetaryKeyword(Base):
    __tablename__ = "planetary_keywords"

    body: Mapped[str] = mapped_column(Text, primary_key=True)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    archetype: Mapped[str] = mapped_column(Text, nullable=False)
    domain_affinities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )


class AspectKeyword(Base):
    __tablename__ = "aspect_keywords"

    aspect_type: Mapped[str] = mapped_column(Text, primary_key=True)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    archetype: Mapped[str] = mapped_column(Text, nullable=False)
