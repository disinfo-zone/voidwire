"""Distillation stage - extract cultural signals via LLM."""
from __future__ import annotations
import logging
import uuid
from datetime import date
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import CulturalSignal, LLMConfig
from voidwire.services.llm_client import LLMClient, LLMSlotConfig, generate_with_validation
from voidwire.services.pipeline_settings import DistillationSettings
from pipeline.prompts.distillation import build_distillation_prompt

logger = logging.getLogger(__name__)
VALID_DOMAINS = {"conflict","diplomacy","economy","technology","culture","environment","social","anomalous","legal","health"}

def _validate_signals(data: Any) -> None:
    if not isinstance(data, list):
        raise ValueError("Expected JSON array")
    for i, s in enumerate(data):
        if not isinstance(s, dict) or "summary" not in s:
            raise ValueError(f"Signal {i} invalid")

async def _get_llm_client(session: AsyncSession, slot: str) -> LLMClient:
    result = await session.execute(select(LLMConfig).where(LLMConfig.slot == slot, LLMConfig.is_active == True))
    config = result.scalars().first()
    if not config:
        raise ValueError(f"No active LLM config for slot: {slot}")
    client = LLMClient()
    client.configure_slot(LLMSlotConfig(
        slot=slot, provider_name=config.provider_name, api_endpoint=config.api_endpoint,
        model_id=config.model_id, api_key_encrypted=config.api_key_encrypted,
        max_tokens=config.max_tokens, temperature=config.temperature or 0.3,
    ))
    return client

async def run_distillation_stage(
    articles: list[dict],
    run_id: uuid.UUID,
    date_context: date,
    session: AsyncSession,
    settings: DistillationSettings | None = None,
) -> list[dict]:
    if not articles:
        return []
    ds = settings or DistillationSettings()
    prompt = build_distillation_prompt(
        articles,
        content_truncation=ds.content_truncation,
        target_signals_min=ds.target_signals_min,
        target_signals_max=ds.target_signals_max,
    )
    try:
        client = await _get_llm_client(session, "distillation")
        signals = await generate_with_validation(client, "distillation", [{"role":"user","content":prompt}], _validate_signals)
        await client.close()
    except Exception as e:
        logger.error("LLM distillation failed: %s", e)
        signals = [{"summary": a.get("title",""), "domain": a.get("domain","anomalous"), "intensity":"minor", "directionality":"stable", "entities":[], "source_refs":[]} for a in articles[:20]]
    stored = []
    for i, signal in enumerate(signals):
        sid = f"sig_{date_context.strftime('%Y%m%d')}_{i+1:03d}"
        db_signal = CulturalSignal(id=sid, date_context=date_context, run_id=run_id,
            summary=signal.get("summary",""), domain=signal.get("domain","anomalous").lower(),
            intensity=signal.get("intensity","minor").lower(), directionality=signal.get("directionality","stable").lower(),
            entities=signal.get("entities",[]), source_refs=signal.get("source_refs",[]))
        session.add(db_signal)
        stored.append({"id": sid, **signal})
    return stored
