"""Update ck_llm_slot CHECK constraint to add personal_free and personal_pro.

Revision ID: 006_llm_slots
Revises: 005_token_tables
Create Date: 2026-02-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "006_llm_slots"
down_revision: Union[str, None] = "005_token_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_llm_slot", "llm_config", type_="check")
    op.create_check_constraint(
        "ck_llm_slot",
        "llm_config",
        "slot IN ('synthesis','distillation','embedding','personal_free','personal_pro')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_llm_slot", "llm_config", type_="check")
    op.create_check_constraint(
        "ck_llm_slot",
        "llm_config",
        "slot IN ('synthesis','distillation','embedding')",
    )
