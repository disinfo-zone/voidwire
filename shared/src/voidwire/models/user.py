"""User account model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voidwire.models.base import Base

if TYPE_CHECKING:
    from voidwire.models.personal_reading import PersonalReading
    from voidwire.models.subscription import Subscription
    from voidwire.models.user_profile import UserProfile


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    password_hash: Mapped[str | None] = mapped_column(Text)
    google_id: Mapped[str | None] = mapped_column(Text, unique=True)
    apple_id: Mapped[str | None] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    pro_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    pro_override_reason: Mapped[str | None] = mapped_column(Text)
    pro_override_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    profile: Mapped[UserProfile] = relationship(
        back_populates="user", uselist=False, lazy="selectin"
    )
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="user", lazy="selectin")
    personal_readings: Mapped[list[PersonalReading]] = relationship(
        back_populates="user", lazy="noload"
    )

    __table_args__ = (
        Index(
            "idx_users_google_id",
            "google_id",
            unique=True,
            postgresql_where=text("google_id IS NOT NULL"),
        ),
        Index(
            "idx_users_apple_id",
            "apple_id",
            unique=True,
            postgresql_where=text("apple_id IS NOT NULL"),
        ),
        Index("idx_users_pro_override_until", "pro_override", "pro_override_until"),
    )
