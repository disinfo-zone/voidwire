"""Admin thread management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AdminUser, CulturalSignal, CulturalThread, ThreadSignal

from api.dependencies import get_db, require_admin

router = APIRouter()


class ThreadUpdateRequest(BaseModel):
    canonical_summary: str | None = None
    domain: str | None = None
    active: bool | None = None


def _thread_dict(t: CulturalThread) -> dict:
    return {
        "id": str(t.id),
        "canonical_summary": t.canonical_summary,
        "domain": t.domain,
        "active": t.active,
        "appearances": t.appearances,
        "first_surfaced": t.first_surfaced.isoformat() if t.first_surfaced else None,
        "last_seen": t.last_seen.isoformat() if t.last_seen else None,
        "mapped_transits": t.mapped_transits,
    }


@router.get("/")
async def list_threads(
    active: bool | None = None,
    domain: str | None = None,
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    query = select(CulturalThread).order_by(CulturalThread.last_seen.desc())
    if active is not None:
        query = query.where(CulturalThread.active == active)
    if domain:
        query = query.where(CulturalThread.domain == domain)
    result = await db.execute(query.offset((page - 1) * 20).limit(20))
    return [_thread_dict(t) for t in result.scalars().all()]


@router.get("/{thread_id}")
async def get_thread(
    thread_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)
):
    t = await db.get(CulturalThread, thread_id)
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    # Also fetch associated signal count
    count_result = await db.execute(select(func.count()).where(ThreadSignal.thread_id == thread_id))
    signal_count = count_result.scalar() or 0
    return {**_thread_dict(t), "signal_count": signal_count}


@router.patch("/{thread_id}")
async def update_thread(
    thread_id: UUID,
    req: ThreadUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    t = await db.get(CulturalThread, thread_id)
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    if req.canonical_summary is not None:
        t.canonical_summary = req.canonical_summary
    if req.domain is not None:
        t.domain = req.domain
    if req.active is not None:
        t.active = req.active
    return {"status": "ok"}


@router.delete("/{thread_id}")
async def deactivate_thread(
    thread_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)
):
    t = await db.get(CulturalThread, thread_id)
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    t.active = False
    return {"status": "deactivated"}


@router.get("/{thread_id}/signals")
async def get_thread_signals(
    thread_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)
):
    t = await db.get(CulturalThread, thread_id)
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    result = await db.execute(
        select(ThreadSignal, CulturalSignal)
        .join(CulturalSignal, CulturalSignal.id == ThreadSignal.signal_id)
        .where(ThreadSignal.thread_id == thread_id)
        .order_by(ThreadSignal.date_seen.desc())
    )
    return [
        {
            "signal_id": row.CulturalSignal.id,
            "summary": row.CulturalSignal.summary,
            "domain": row.CulturalSignal.domain,
            "intensity": row.CulturalSignal.intensity,
            "date_seen": row.ThreadSignal.date_seen.isoformat()
            if row.ThreadSignal.date_seen
            else None,
            "similarity_score": row.ThreadSignal.similarity_score,
        }
        for row in result.all()
    ]
