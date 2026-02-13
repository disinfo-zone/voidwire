"""Admin news source management."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import NewsSource, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

class SourceCreateRequest(BaseModel):
    name: str
    source_type: str = "rss"
    url: str
    domain: str = "anomalous"
    weight: float = 0.5

@router.get("/")
async def list_sources(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(NewsSource).order_by(NewsSource.name))
    return [{"id": str(s.id), "name": s.name, "source_type": s.source_type, "url": s.url, "domain": s.domain, "weight": s.weight, "status": s.status, "last_error": s.last_error} for s in result.scalars().all()]

@router.post("/")
async def create_source(req: SourceCreateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    source = NewsSource(name=req.name, source_type=req.source_type, url=req.url, domain=req.domain, weight=req.weight)
    db.add(source)
    await db.flush()
    return {"id": str(source.id), "status": "created"}

@router.delete("/{source_id}")
async def delete_source(source_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    source = await db.get(NewsSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    return {"status": "deleted"}
