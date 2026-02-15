"""Admin signal browsing."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AdminUser, CulturalSignal

from api.dependencies import get_db, require_admin

router = APIRouter()


def _signal_dict(s: CulturalSignal) -> dict:
    return {
        "id": s.id,
        "date_context": s.date_context.isoformat(),
        "run_id": str(s.run_id) if s.run_id else None,
        "summary": s.summary,
        "domain": s.domain,
        "intensity": s.intensity,
        "directionality": s.directionality,
        "entities": s.entities,
        "source_refs": s.source_refs,
        "was_selected": s.was_selected,
        "was_wild_card": s.was_wild_card,
        "selection_weight": s.selection_weight,
    }


@router.get("/")
async def list_signals(
    date_from: str | None = None,
    date_to: str | None = None,
    domain: str | None = None,
    intensity: str | None = None,
    selected_only: bool = False,
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    query = select(CulturalSignal).order_by(CulturalSignal.date_context.desc())
    if date_from:
        query = query.where(CulturalSignal.date_context >= date.fromisoformat(date_from))
    if date_to:
        query = query.where(CulturalSignal.date_context <= date.fromisoformat(date_to))
    if domain:
        query = query.where(CulturalSignal.domain == domain)
    if intensity:
        query = query.where(CulturalSignal.intensity == intensity)
    if selected_only:
        query = query.where(CulturalSignal.was_selected)
    result = await db.execute(query.offset((page - 1) * 50).limit(50))
    return [_signal_dict(s) for s in result.scalars().all()]


@router.get("/stats")
async def signal_stats(
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    base = select(CulturalSignal)
    if date_from:
        base = base.where(CulturalSignal.date_context >= date.fromisoformat(date_from))
    if date_to:
        base = base.where(CulturalSignal.date_context <= date.fromisoformat(date_to))

    # Domain distribution
    domain_result = await db.execute(
        select(CulturalSignal.domain, func.count())
        .where(base.whereclause if base.whereclause is not None else True)
        .group_by(CulturalSignal.domain)
    )
    domain_stats = {row[0]: row[1] for row in domain_result.all()}

    # Intensity distribution
    intensity_result = await db.execute(
        select(CulturalSignal.intensity, func.count())
        .where(base.whereclause if base.whereclause is not None else True)
        .group_by(CulturalSignal.intensity)
    )
    intensity_stats = {row[0]: row[1] for row in intensity_result.all()}

    # Total count
    total_result = await db.execute(
        select(func.count())
        .select_from(CulturalSignal)
        .where(base.whereclause if base.whereclause is not None else True)
    )
    total = total_result.scalar() or 0

    return {
        "total": total,
        "by_domain": domain_stats,
        "by_intensity": intensity_stats,
    }


@router.get("/{signal_id}")
async def get_signal(
    signal_id: str, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)
):
    s = await db.get(CulturalSignal, signal_id)
    if not s:
        raise HTTPException(status_code=404, detail="Signal not found")
    return _signal_dict(s)
