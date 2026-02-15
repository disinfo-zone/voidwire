"""User birth data and natal chart profile."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voidwire.models.base import Base

if TYPE_CHECKING:
    from voidwire.models.user import User


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_time: Mapped[time | None] = mapped_column(Time)
    birth_time_known: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    birth_city: Mapped[str] = mapped_column(Text, nullable=False)
    birth_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    birth_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    birth_timezone: Mapped[str] = mapped_column(Text, nullable=False)
    house_system: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'placidus'"))
    natal_chart_json: Mapped[dict | None] = mapped_column(JSONB)
    natal_chart_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    user: Mapped[User] = relationship(back_populates="profile")

    __table_args__ = (
        CheckConstraint(
            "house_system IN ('placidus','whole_sign','koch','equal','porphyry')",
            name="ck_house_system",
        ),
    )
