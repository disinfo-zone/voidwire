"""Pipeline run model - immutable record of every generation attempt."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Integer,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voidwire.models.base import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    date_context: Mapped[date] = mapped_column(Date, nullable=False)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'running'")
    )

    # Reproducibility inputs
    code_version: Mapped[str] = mapped_column(Text, nullable=False)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    template_versions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_config_json: Mapped[dict] = mapped_column("model_config", JSONB, nullable=False)
    regeneration_mode: Mapped[str | None] = mapped_column(Text)
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id")
    )
    reused_artifacts: Mapped[dict | None] = mapped_column(JSONB)

    # Persisted artifacts
    ephemeris_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    distilled_signals: Mapped[dict] = mapped_column(JSONB, nullable=False)
    selected_signals: Mapped[dict] = mapped_column(JSONB, nullable=False)
    wild_card_signal_id: Mapped[str | None] = mapped_column(Text)
    wild_card_distances: Mapped[dict | None] = mapped_column(JSONB)
    thread_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prompt_payloads: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Content hashes
    ephemeris_hash: Mapped[str] = mapped_column(Text, nullable=False)
    distillation_hash: Mapped[str] = mapped_column(Text, nullable=False)
    selection_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Outputs
    interpretive_plan: Mapped[dict | None] = mapped_column(JSONB)
    generated_output: Mapped[dict | None] = mapped_column(JSONB)
    error_detail: Mapped[str | None] = mapped_column(Text)
    pruned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    readings: Mapped[list["Reading"]] = relationship(back_populates="run", foreign_keys="Reading.run_id")

    __table_args__ = (
        UniqueConstraint("date_context", "run_number"),
        CheckConstraint("status IN ('running','completed','failed')", name="ck_pipeline_status"),
        Index("idx_pipeline_runs_date", "date_context", postgresql_using="btree"),
    )
