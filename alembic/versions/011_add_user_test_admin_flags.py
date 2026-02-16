"""Add user test/admin role flags for public account controls.

Revision ID: 011_user_test_admin_flags
Revises: 010_admin_rbac_async_jobs
Create Date: 2026-02-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011_user_test_admin_flags"
down_revision: str | None = "010_admin_rbac_async_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_test_user", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    op.add_column(
        "users",
        sa.Column("is_admin_user", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin_user")
    op.drop_column("users", "is_test_user")

