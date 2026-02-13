"""Thread tracking stage."""
from __future__ import annotations
import logging
import math
import uuid
from datetime import date, timedelta
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import CulturalThread, ThreadSignal
from voidwire.services.pipeline_settings import ThreadSettings

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _recency_weighted_centroid(old: list[float], new: list[float], decay: float) -> list[float]:
    """Compute recency-weighted centroid: decay * old + (1-decay) * new."""
    return [decay * o + (1 - decay) * n for o, n in zip(old, new)]


async def run_thread_stage(
    signals: list[dict],
    date_context: date,
    session: AsyncSession,
    settings: ThreadSettings | None = None,
) -> list[dict]:
    ts = settings or ThreadSettings()
    # Fetch all threads (active and recently deactivated for reactivation)
    reactivation_cutoff = date_context - timedelta(days=ts.deactivation_days * ts.reactivation_multiplier)
    result = await session.execute(
        select(CulturalThread).where(
            (CulturalThread.active == True) |
            ((CulturalThread.active == False) & (CulturalThread.last_seen >= reactivation_cutoff))
        )
    )
    all_threads = list(result.scalars().all())
    active_threads = [t for t in all_threads if t.active]
    inactive_threads = [t for t in all_threads if not t.active]

    for signal in signals:
        emb = signal.get("embedding")
        if not emb:
            continue

        best_match, best_score = None, 0.0
        search_pool = active_threads + inactive_threads

        for thread in search_pool:
            if thread.centroid_embedding is None:
                continue
            centroid = list(thread.centroid_embedding) if hasattr(thread.centroid_embedding, '__iter__') else []
            if not centroid:
                continue
            sim = _cosine_similarity(emb, centroid)
            bonus = ts.domain_bonus if signal.get("domain") == thread.domain else 0.0
            score = sim + bonus
            if score > ts.match_threshold and score > best_score:
                best_match, best_score = thread, score

        if best_match:
            # Reactivate if the thread was inactive
            if not best_match.active:
                best_match.active = True
                if best_match not in active_threads:
                    active_threads.append(best_match)
                    inactive_threads = [t for t in inactive_threads if t.id != best_match.id]
                logger.info("Reactivated thread %s: %s", best_match.id, best_match.canonical_summary[:60])

            best_match.last_seen = date_context
            best_match.appearances += 1

            # Recency-weighted centroid update
            if best_match.centroid_embedding is not None:
                old_centroid = list(best_match.centroid_embedding) if hasattr(best_match.centroid_embedding, '__iter__') else []
                if old_centroid and len(old_centroid) == len(emb):
                    best_match.centroid_embedding = _recency_weighted_centroid(old_centroid, emb, ts.centroid_decay)

            # Update canonical summary only when match is very high
            # (signal is clearly the same story in updated form)
            if best_score > ts.summary_update_threshold:
                best_match.canonical_summary = signal.get("summary", best_match.canonical_summary)

            if signal.get("id"):
                session.add(ThreadSignal(
                    thread_id=best_match.id,
                    signal_id=signal["id"],
                    date_seen=date_context,
                    similarity_score=best_score,
                ))
        else:
            # Create new thread
            new_thread = CulturalThread(
                id=uuid.uuid4(),
                canonical_summary=signal.get("summary", ""),
                domain=signal.get("domain", "anomalous"),
                first_surfaced=date_context,
                last_seen=date_context,
                centroid_embedding=emb,
            )
            session.add(new_thread)
            active_threads.append(new_thread)

    # Deactivate stale threads
    cutoff = date_context - timedelta(days=ts.deactivation_days)
    await session.execute(
        update(CulturalThread)
        .where(CulturalThread.active == True, CulturalThread.last_seen < cutoff)
        .values(active=False)
    )

    # Return active thread snapshot
    result = await session.execute(select(CulturalThread).where(CulturalThread.active == True))
    return [
        {
            "id": str(t.id),
            "canonical_summary": t.canonical_summary,
            "domain": t.domain,
            "appearances": t.appearances,
            "first_surfaced": t.first_surfaced.isoformat() if t.first_surfaced else None,
            "last_seen": t.last_seen.isoformat() if t.last_seen else None,
        }
        for t in result.scalars().all()
    ]
