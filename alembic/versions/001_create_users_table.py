"""Create users table.

Revision ID: 001_users
Revises:
Create Date: 2026-02-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001_users"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("google_id", sa.Text(), nullable=True),
        sa.Column("apple_id", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_users_google_id", "users", ["google_id"],
        unique=True, postgresql_where=sa.text("google_id IS NOT NULL"),
    )
    op.create_index(
        "idx_users_apple_id", "users", ["apple_id"],
        unique=True, postgresql_where=sa.text("apple_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_users_apple_id", table_name="users")
    op.drop_index("idx_users_google_id", table_name="users")
    op.drop_table("users")
