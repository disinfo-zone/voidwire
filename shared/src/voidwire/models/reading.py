"""Reading model - generated and published artifacts."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voidwire.models.base import Base


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False
    )
    date_context: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )

    # Generated content (immutable once created)
    generated_standard: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_extended: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_annotations: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Published content (may differ from generated if edited)
    published_standard: Mapped[dict | None] = mapped_column(JSONB)
    published_extended: Mapped[dict | None] = mapped_column(JSONB)
    published_annotations: Mapped[dict | None] = mapped_column(JSONB)

    # Editorial
    editorial_diff: Mapped[dict | None] = mapped_column(JSONB)
    editorial_notes: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    # Relationships
    run: Mapped["PipelineRun"] = relationship(back_populates="readings", foreign_keys=[run_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','published','archived')",
            name="ck_reading_status",
        ),
        Index("idx_readings_date", "date_context", postgresql_using="btree"),
        Index("idx_readings_status", "status"),
        Index(
            "idx_readings_one_published",
            "date_context",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
    )
