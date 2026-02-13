"""Setup state model - tracks first-run wizard completion."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from voidwire.models.base import Base


class SetupState(Base):
    __tablename__ = "setup_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default=text("1"))
    is_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    steps_completed: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    __table_args__ = (CheckConstraint("id = 1", name="ck_setup_singleton"),)
