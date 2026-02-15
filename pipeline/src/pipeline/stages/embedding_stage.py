"""Embedding generation stage."""
from __future__ import annotations
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def run_embedding_stage(signals: list[dict[str, Any]], session: AsyncSession) -> list[dict[str, Any]]:
    if not signals:
        return signals
    texts = [s.get("summary","") for s in signals]
    try:
        from pipeline.stages.distillation_stage import _get_llm_client
        client = await _get_llm_client(session, "embedding")
        embeddings = await client.generate_embeddings("embedding", texts)
        await client.close()
        for signal, emb in zip(signals, embeddings):
            signal["embedding"] = emb
    except Exception as e:
        logger.warning("Embedding generation failed: %s", e)
    return signals
