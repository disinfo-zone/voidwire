"""Add admin roles, token versions, and async job queue table.

Revision ID: 010_admin_rbac_async_jobs
Revises: 009_discount_codes_override
Create Date: 2026-02-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "010_admin_rbac_async_jobs"
down_revision: str | None = "009_discount_codes_override"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'owner'")),
    )
    op.add_column(
        "admin_users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_check_constraint(
        "ck_admin_user_role",
        "admin_users",
        "role IN ('owner','admin','support','readonly')",
    )

    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    op.create_table(
        "async_jobs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed')",
            name="ck_async_job_status",
        ),
    )
    op.create_index(
        "idx_async_jobs_status_created",
        "async_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "idx_async_jobs_user_created",
        "async_jobs",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_async_jobs_user_created", table_name="async_jobs")
    op.drop_index("idx_async_jobs_status_created", table_name="async_jobs")
    op.drop_table("async_jobs")

    op.drop_column("users", "token_version")

    op.drop_constraint("ck_admin_user_role", "admin_users", type_="check")
    op.drop_column("admin_users", "token_version")
    op.drop_column("admin_users", "role")
