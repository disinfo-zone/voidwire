"""Admin readings management."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import Reading, AuditLog, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

class ReadingUpdateRequest(BaseModel):
    status: str | None = None
    published_standard: dict | None = None
    editorial_notes: str | None = None

@router.get("/")
async def list_readings(status: str | None = None, page: int = Query(default=1, ge=1), db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    query = select(Reading).order_by(Reading.date_context.desc())
    if status:
        query = query.where(Reading.status == status)
    result = await db.execute(query.offset((page-1)*20).limit(20))
    return [{"id": str(r.id), "date_context": r.date_context.isoformat(), "status": r.status, "title": (r.generated_standard or {}).get("title",""), "published_at": r.published_at.isoformat() if r.published_at else None} for r in result.scalars().all()]

@router.get("/{reading_id}")
async def get_reading(reading_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    reading = await db.get(Reading, reading_id)
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    return {"id": str(reading.id), "run_id": str(reading.run_id), "date_context": reading.date_context.isoformat(), "status": reading.status, "generated_standard": reading.generated_standard, "generated_extended": reading.generated_extended, "published_standard": reading.published_standard, "published_extended": reading.published_extended, "editorial_notes": reading.editorial_notes}

@router.patch("/{reading_id}")
async def update_reading(reading_id: UUID, req: ReadingUpdateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    reading = await db.get(Reading, reading_id)
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    if req.status:
        reading.status = req.status
        if req.status == "published":
            reading.published_at = datetime.now(timezone.utc)
            reading.published_standard = reading.published_standard or reading.generated_standard
            reading.published_extended = reading.published_extended or reading.generated_extended
            reading.published_annotations = reading.published_annotations or reading.generated_annotations
    if req.editorial_notes:
        reading.editorial_notes = req.editorial_notes
    reading.updated_at = datetime.now(timezone.utc)
    db.add(AuditLog(user_id=user.id, action=f"reading.{req.status or 'edit'}", target_type="reading", target_id=str(reading_id)))
    return {"status": "ok"}
