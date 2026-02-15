"""Create user_profiles table.

Revision ID: 002_user_profiles
Revises: 001_users
Create Date: 2026-02-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "002_user_profiles"
down_revision: str | None = "001_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("birth_time", sa.Time(), nullable=True),
        sa.Column(
            "birth_time_known", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        sa.Column("birth_city", sa.Text(), nullable=False),
        sa.Column("birth_latitude", sa.Float(), nullable=False),
        sa.Column("birth_longitude", sa.Float(), nullable=False),
        sa.Column("birth_timezone", sa.Text(), nullable=False),
        sa.Column("house_system", sa.Text(), nullable=False, server_default=sa.text("'placidus'")),
        sa.Column("natal_chart_json", JSONB(), nullable=True),
        sa.Column("natal_chart_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "house_system IN ('placidus','whole_sign','koch','equal','porphyry')",
            name="ck_house_system",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
