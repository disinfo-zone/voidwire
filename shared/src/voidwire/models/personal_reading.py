"""Personalized reading model."""

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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voidwire.models.base import Base


class PersonalReading(Base):
    __tablename__ = "personal_readings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tier: Mapped[str] = mapped_column(Text, nullable=False)
    date_context: Mapped[date] = mapped_column(Date, nullable=False)
    week_key: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    house_system_used: Mapped[str] = mapped_column(Text, nullable=False)
    llm_slot_used: Mapped[str] = mapped_column(Text, nullable=False)
    generation_metadata: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="personal_readings")

    __table_args__ = (
        CheckConstraint("tier IN ('free','pro')", name="ck_personal_reading_tier"),
        UniqueConstraint("user_id", "tier", "date_context", name="uq_personal_reading_user_tier_date"),
        Index("idx_personal_readings_user_date", "user_id", "date_context"),
        Index("idx_personal_readings_user_week", "user_id", "week_key"),
    )
