"""Cultural thread models - tracked narrative arcs."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from voidwire.models.base import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class CulturalThread(Base):
    __tablename__ = "cultural_threads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_summary: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    first_surfaced: Mapped[date] = mapped_column(Date, nullable=False)
    last_seen: Mapped[date] = mapped_column(Date, nullable=False)
    appearances: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    centroid_embedding = mapped_column(Vector(1536) if Vector else Text, nullable=True)
    mapped_transits: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    _base_args = [
        Index("idx_threads_active", "active", "last_seen", postgresql_using="btree"),
    ]
    if Vector:
        _base_args.append(Index(
            "idx_threads_embedding", "centroid_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"centroid_embedding": "vector_cosine_ops"},
        ))
    __table_args__ = tuple(_base_args)


class ThreadSignal(Base):
    __tablename__ = "thread_signals"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cultural_threads.id"), primary_key=True
    )
    signal_id: Mapped[str] = mapped_column(
        Text, ForeignKey("cultural_signals.id"), primary_key=True
    )
    date_seen: Mapped[date] = mapped_column(Date, nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
