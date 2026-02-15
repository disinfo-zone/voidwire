"""Create personal_readings table.

Revision ID: 004_personal_readings
Revises: 003_subscriptions
Create Date: 2026-02-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "004_personal_readings"
down_revision: Union[str, None] = "003_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "personal_readings",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("date_context", sa.Date(), nullable=False),
        sa.Column("week_key", sa.Text(), nullable=True),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("house_system_used", sa.Text(), nullable=False),
        sa.Column("llm_slot_used", sa.Text(), nullable=False),
        sa.Column("generation_metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("tier IN ('free','pro')", name="ck_personal_reading_tier"),
        sa.UniqueConstraint("user_id", "tier", "date_context", name="uq_personal_reading_user_tier_date"),
    )
    op.create_index("idx_personal_readings_user_date", "personal_readings", ["user_id", "date_context"])
    op.create_index("idx_personal_readings_user_week", "personal_readings", ["user_id", "week_key"])


def downgrade() -> None:
    op.drop_index("idx_personal_readings_user_week", table_name="personal_readings")
    op.drop_index("idx_personal_readings_user_date", table_name="personal_readings")
    op.drop_table("personal_readings")
