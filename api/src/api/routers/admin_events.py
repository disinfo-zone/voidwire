"""Admin events management."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AstronomicalEvent, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

@router.get("/")
async def list_events(limit: int = Query(default=50), db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(AstronomicalEvent).order_by(AstronomicalEvent.at.desc()).limit(limit))
    return [{"id": str(e.id), "event_type": e.event_type, "body": e.body, "sign": e.sign, "at": e.at.isoformat(), "significance": e.significance, "reading_status": e.reading_status} for e in result.scalars().all()]
