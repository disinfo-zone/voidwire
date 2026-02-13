"""Astronomical event model - pre-calculated major events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from voidwire.models.base import Base


class AstronomicalEvent(Base):
    __tablename__ = "astronomical_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    sign: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    significance: Mapped[str] = mapped_column(Text, nullable=False)
    ephemeris_data: Mapped[dict | None] = mapped_column(JSONB)

    # Generated reading
    reading_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    reading_title: Mapped[str | None] = mapped_column(Text)
    reading_body: Mapped[str | None] = mapped_column(Text)
    reading_extended: Mapped[dict | None] = mapped_column(JSONB)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_url: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('new_moon','full_moon','lunar_eclipse','solar_eclipse',"
            "'retrograde_station','direct_station','ingress_major')",
            name="ck_event_type",
        ),
        CheckConstraint(
            "significance IN ('major','moderate','minor')", name="ck_event_significance"
        ),
        CheckConstraint(
            "reading_status IN ('pending','generated','published','skipped')",
            name="ck_event_reading_status",
        ),
        Index("idx_events_date", "at", postgresql_using="btree"),
        Index("idx_events_type", "event_type", "at", postgresql_using="btree"),
    )
