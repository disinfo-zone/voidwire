"""Admin archetypal dictionary."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
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

@router.get("/")
async def list_meanings(page: int = Query(default=1, ge=1), db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(ArchetypalMeaning).offset((page-1)*50).limit(50))
    return [{"id": str(m.id), "body1": m.body1, "body2": m.body2, "aspect_type": m.aspect_type, "event_type": m.event_type, "core_meaning": m.core_meaning, "keywords": m.keywords, "source": m.source} for m in result.scalars().all()]

@router.post("/")
async def create_meaning(req: MeaningRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    m = ArchetypalMeaning(body1=req.body1, body2=req.body2, aspect_type=req.aspect_type, event_type=req.event_type, core_meaning=req.core_meaning, keywords=req.keywords, domain_affinities=req.domain_affinities, source=req.source)
    db.add(m)
    await db.flush()
    return {"id": str(m.id)}
