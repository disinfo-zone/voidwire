"""Add lookup indexes for token tables.

Revision ID: 008_token_indexes
Revises: 007_stripe_webhook_events
Create Date: 2026-02-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "008_token_indexes"
down_revision: str | None = "007_stripe_webhook_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_email_verification_token_hash",
        "email_verification_tokens",
        ["token_hash"],
    )
    op.create_index(
        "idx_email_verification_user_expires",
        "email_verification_tokens",
        ["user_id", "expires_at"],
    )
    op.create_index(
        "idx_password_reset_token_hash",
        "password_reset_tokens",
        ["token_hash"],
    )
    op.create_index(
        "idx_password_reset_user_expires",
        "password_reset_tokens",
        ["user_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_password_reset_user_expires", table_name="password_reset_tokens")
    op.drop_index("idx_password_reset_token_hash", table_name="password_reset_tokens")
    op.drop_index("idx_email_verification_user_expires", table_name="email_verification_tokens")
    op.drop_index("idx_email_verification_token_hash", table_name="email_verification_tokens")
