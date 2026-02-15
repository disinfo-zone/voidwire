"""LLM slot defaults and bootstrap helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import LLMConfig

DEFAULT_LLM_SLOTS = ("distillation", "embedding", "personal_free", "personal_pro", "synthesis")


def _build_default_slot(slot: str) -> LLMConfig:
    """Create an editable default LLM slot with safe inactive defaults."""
    return LLMConfig(
        slot=slot,
        provider_name="",
        api_endpoint="",
        model_id="",
        api_key_encrypted="",
        extra_params={},
        is_active=False,
    )


async def ensure_default_llm_slots(db: AsyncSession) -> list[LLMConfig]:
    """Ensure canonical LLM slots exist and return them in stable order."""
    result = await db.execute(select(LLMConfig))
    existing = list(result.scalars().all())
    by_slot = {slot_cfg.slot: slot_cfg for slot_cfg in existing}

    created = False
    for slot in DEFAULT_LLM_SLOTS:
        if slot not in by_slot:
            slot_cfg = _build_default_slot(slot)
            db.add(slot_cfg)
            by_slot[slot] = slot_cfg
            created = True

    if created:
        await db.flush()

    return [by_slot[slot] for slot in sorted(DEFAULT_LLM_SLOTS)]
