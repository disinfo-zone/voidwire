"""Cultural signal model - individual distilled signals."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from voidwire.models.base import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class CulturalSignal(Base):
    __tablename__ = "cultural_signals"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # sig_YYYYMMDD_NNN
    date_context: Mapped[date] = mapped_column(Date, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id")
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    intensity: Mapped[str] = mapped_column(Text, nullable=False)
    directionality: Mapped[str] = mapped_column(Text, nullable=False)
    entities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    source_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )

    embedding = mapped_column(Vector(1536) if Vector else Text, nullable=True)
    was_selected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    was_wild_card: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    selection_weight: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    _base_args = [
        CheckConstraint(
            "domain IN ('conflict','diplomacy','economy','technology','culture',"
            "'environment','social','anomalous','legal','health')",
            name="ck_signal_domain",
        ),
        CheckConstraint(
            "intensity IN ('major','moderate','minor')",
            name="ck_signal_intensity",
        ),
        CheckConstraint(
            "directionality IN ('escalating','stable','de-escalating','erupting','resolving')",
            name="ck_signal_directionality",
        ),
        Index("idx_signals_date", "date_context", postgresql_using="btree"),
    ]
    if Vector:
        _base_args.append(
            Index(
                "idx_signals_embedding",
                "embedding",
                postgresql_using="hnsw",
                postgresql_with={"m": 16, "ef_construction": 64},
                postgresql_ops={"embedding": "vector_cosine_ops"},
            )
        )
    __table_args__ = tuple(_base_args)
