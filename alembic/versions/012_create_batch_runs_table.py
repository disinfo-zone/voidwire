"""Create batch_runs table for tracking batch execution.

Revision ID: 012_create_batch_runs
Revises: 011_user_test_admin_flags
Create Date: 2026-02-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "012_create_batch_runs"
down_revision: str | None = "011_user_test_admin_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "batch_runs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("batch_type", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("week_key", sa.Text(), nullable=True),
        sa.Column("eligible_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("generated_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("non_latin_fix_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("summary_json", JSONB(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','completed','failed')",
            name="ck_batch_run_status",
        ),
    )
    op.create_index(
        "idx_batch_runs_type_started",
        "batch_runs",
        ["batch_type", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_batch_runs_type_started", table_name="batch_runs")
    op.drop_table("batch_runs")
