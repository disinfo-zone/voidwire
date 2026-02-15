"""Add discount codes table and user pro override fields.

Revision ID: 009_discount_codes_override
Revises: 008_token_indexes
Create Date: 2026-02-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "009_discount_codes_override"
down_revision: str | None = "008_token_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("pro_override", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    op.add_column("users", sa.Column("pro_override_reason", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("pro_override_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "idx_users_pro_override_until",
        "users",
        ["pro_override", "pro_override_until"],
    )

    op.create_table(
        "discount_codes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("stripe_coupon_id", sa.Text(), nullable=False, unique=True),
        sa.Column("stripe_promotion_code_id", sa.Text(), nullable=False, unique=True),
        sa.Column("percent_off", sa.Numeric(5, 2), nullable=True),
        sa.Column("amount_off_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("duration", sa.Text(), nullable=False, server_default=sa.text("'once'")),
        sa.Column("duration_in_months", sa.Integer(), nullable=True),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_by_admin_id",
            UUID(as_uuid=True),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "duration IN ('once','forever','repeating')",
            name="ck_discount_code_duration",
        ),
        sa.CheckConstraint(
            "percent_off IS NULL OR (percent_off > 0 AND percent_off <= 100)",
            name="ck_discount_code_percent_off",
        ),
        sa.CheckConstraint(
            "amount_off_cents IS NULL OR amount_off_cents > 0",
            name="ck_discount_code_amount_off_cents",
        ),
        sa.CheckConstraint(
            "max_redemptions IS NULL OR max_redemptions > 0",
            name="ck_discount_code_max_redemptions",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR starts_at IS NULL OR expires_at > starts_at",
            name="ck_discount_code_window",
        ),
    )
    op.create_index("idx_discount_codes_code", "discount_codes", ["code"])
    op.create_index(
        "idx_discount_codes_active_window",
        "discount_codes",
        ["is_active", "starts_at", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_discount_codes_active_window", table_name="discount_codes")
    op.drop_index("idx_discount_codes_code", table_name="discount_codes")
    op.drop_table("discount_codes")

    op.drop_index("idx_users_pro_override_until", table_name="users")
    op.drop_column("users", "pro_override_until")
    op.drop_column("users", "pro_override_reason")
    op.drop_column("users", "pro_override")
