"""Admin archetypal dictionary."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AdminUser
from voidwire.models.archetypal_meaning import ArchetypalMeaning

from api.dependencies import get_db, require_admin

router = APIRouter()


class MeaningRequest(BaseModel):
    body1: str
    body2: str | None = None
    aspect_type: str | None = None
    event_type: str = "aspect"
    core_meaning: str
    keywords: list[str] = []
    domain_affinities: list[str] = []
    source: str = "curated"


class MeaningUpdateRequest(BaseModel):
    body1: str | None = None
    body2: str | None = None
    aspect_type: str | None = None
    event_type: str | None = None
    core_meaning: str | None = None
    keywords: list[str] | None = None
    domain_affinities: list[str] | None = None
    source: str | None = None


def _meaning_dict(m: ArchetypalMeaning) -> dict:
    return {
        "id": str(m.id),
        "body1": m.body1,
        "body2": m.body2,
        "aspect_type": m.aspect_type,
        "event_type": m.event_type,
        "core_meaning": m.core_meaning,
        "keywords": m.keywords,
        "domain_affinities": m.domain_affinities,
        "source": m.source,
    }


@router.get("/")
async def list_meanings(
    page: int = Query(default=1, ge=1),
    body1: str | None = None,
    body2: str | None = None,
    event_type: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    query = select(ArchetypalMeaning)
    if body1:
        query = query.where(ArchetypalMeaning.body1 == body1)
    if body2:
        query = query.where(ArchetypalMeaning.body2 == body2)
    if event_type:
        query = query.where(ArchetypalMeaning.event_type == event_type)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                ArchetypalMeaning.core_meaning.ilike(pattern),
                ArchetypalMeaning.body1.ilike(pattern),
            )
        )
    result = await db.execute(query.offset((page - 1) * 50).limit(50))
    return [_meaning_dict(m) for m in result.scalars().all()]


@router.get("/{meaning_id}")
async def get_meaning(
    meaning_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)
):
    m = await db.get(ArchetypalMeaning, meaning_id)
    if not m:
        raise HTTPException(status_code=404, detail="Meaning not found")
    return _meaning_dict(m)


@router.post("/")
async def create_meaning(
    req: MeaningRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    m = ArchetypalMeaning(
        body1=req.body1,
        body2=req.body2,
        aspect_type=req.aspect_type,
        event_type=req.event_type,
        core_meaning=req.core_meaning,
        keywords=req.keywords,
        domain_affinities=req.domain_affinities,
        source=req.source,
    )
    db.add(m)
    await db.flush()
    return {"id": str(m.id)}


@router.patch("/{meaning_id}")
async def update_meaning(
    meaning_id: UUID,
    req: MeaningUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    m = await db.get(ArchetypalMeaning, meaning_id)
    if not m:
        raise HTTPException(status_code=404, detail="Meaning not found")
    for field in (
        "body1",
        "body2",
        "aspect_type",
        "event_type",
        "core_meaning",
        "keywords",
        "domain_affinities",
        "source",
    ):
        val = getattr(req, field, None)
        if val is not None:
            setattr(m, field, val)
    return {"status": "ok"}


@router.delete("/{meaning_id}")
async def delete_meaning(
    meaning_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)
):
    m = await db.get(ArchetypalMeaning, meaning_id)
    if not m:
        raise HTTPException(status_code=404, detail="Meaning not found")
    await db.delete(m)
    return {"status": "deleted"}


@router.post("/bulk-import")
async def bulk_import(
    entries: list[MeaningRequest],
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    created = []
    for req in entries:
        m = ArchetypalMeaning(
            body1=req.body1,
            body2=req.body2,
            aspect_type=req.aspect_type,
            event_type=req.event_type,
            core_meaning=req.core_meaning,
            keywords=req.keywords,
            domain_affinities=req.domain_affinities,
            source=req.source,
        )
        db.add(m)
        await db.flush()
        created.append(str(m.id))
    return {"status": "ok", "count": len(created), "ids": created}
