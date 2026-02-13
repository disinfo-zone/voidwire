"""Thread tracking stage."""
from __future__ import annotations
import logging
import uuid
from datetime import date, timedelta
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import CulturalThread, ThreadSignal

logger = logging.getLogger(__name__)
THREAD_MATCH_THRESHOLD = 0.75

async def run_thread_stage(signals: list[dict], date_context: date, session: AsyncSession) -> list[dict]:
    result = await session.execute(select(CulturalThread).where(CulturalThread.active == True))
    active_threads = list(result.scalars().all())
    for signal in signals:
        emb = signal.get("embedding")
        if not emb:
            continue
        best_match, best_score = None, 0.0
        for thread in active_threads:
            if thread.centroid_embedding is None:
                continue
            centroid = list(thread.centroid_embedding) if hasattr(thread.centroid_embedding, '__iter__') else []
            if not centroid:
                continue
            from pipeline.stages.selection_stage import _cosine_similarity
            sim = _cosine_similarity(emb, centroid)
            bonus = 0.1 if signal.get("domain") == thread.domain else 0.0
            score = sim + bonus
            if score > THREAD_MATCH_THRESHOLD and score > best_score:
                best_match, best_score = thread, score
        if best_match:
            best_match.last_seen = date_context
            best_match.appearances += 1
            if signal.get("id"):
                session.add(ThreadSignal(thread_id=best_match.id, signal_id=signal["id"], date_seen=date_context, similarity_score=best_score))
        else:
            new_thread = CulturalThread(id=uuid.uuid4(), canonical_summary=signal.get("summary",""), domain=signal.get("domain","anomalous"), first_surfaced=date_context, last_seen=date_context, centroid_embedding=emb)
            session.add(new_thread)
            active_threads.append(new_thread)
    cutoff = date_context - timedelta(days=7)
    await session.execute(update(CulturalThread).where(CulturalThread.active == True, CulturalThread.last_seen < cutoff).values(active=False))
    result = await session.execute(select(CulturalThread).where(CulturalThread.active == True))
    return [{"id": str(t.id), "canonical_summary": t.canonical_summary, "domain": t.domain, "appearances": t.appearances} for t in result.scalars().all()]
