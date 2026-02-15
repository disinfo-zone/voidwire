"""Admin-managed discount codes mapped to Stripe promotion codes."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from voidwire.models.base import Base


class DiscountCode(Base):
    __tablename__ = "discount_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    stripe_coupon_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    stripe_promotion_code_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    percent_off: Mapped[float | None] = mapped_column(Numeric(5, 2))
    amount_off_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(Text)
    duration: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'once'"))
    duration_in_months: Mapped[int | None] = mapped_column(Integer)
    max_redemptions: Mapped[int | None] = mapped_column(Integer)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        CheckConstraint(
            "duration IN ('once','forever','repeating')",
            name="ck_discount_code_duration",
        ),
        CheckConstraint(
            "percent_off IS NULL OR (percent_off > 0 AND percent_off <= 100)",
            name="ck_discount_code_percent_off",
        ),
        CheckConstraint(
            "amount_off_cents IS NULL OR amount_off_cents > 0",
            name="ck_discount_code_amount_off_cents",
        ),
        CheckConstraint(
            "max_redemptions IS NULL OR max_redemptions > 0",
            name="ck_discount_code_max_redemptions",
        ),
        CheckConstraint(
            "expires_at IS NULL OR starts_at IS NULL OR expires_at > starts_at",
            name="ck_discount_code_window",
        ),
        Index("idx_discount_codes_code", "code"),
        Index(
            "idx_discount_codes_active_window",
            "is_active",
            "starts_at",
            "expires_at",
        ),
    )
