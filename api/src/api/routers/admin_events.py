"""Admin events management."""
from __future__ import annotations
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AstronomicalEvent, AuditLog, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

EventType = Literal[
    "new_moon",
    "full_moon",
    "lunar_eclipse",
    "solar_eclipse",
    "retrograde_station",
    "direct_station",
    "ingress_major",
]
Significance = Literal["major", "moderate", "minor"]
ReadingStatus = Literal["pending", "generated", "published", "skipped"]


class EventCreateRequest(BaseModel):
    event_type: EventType
    body: str | None = None
    sign: str | None = None
    at: str
    significance: Significance = "moderate"
    ephemeris_data: dict | None = None

class EventUpdateRequest(BaseModel):
    event_type: EventType | None = None
    body: str | None = None
    sign: str | None = None
    at: str | None = None
    significance: Significance | None = None
    ephemeris_data: dict | None = None
    reading_status: ReadingStatus | None = None


def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _parse_event_datetime(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Field 'at' is required and must be a valid datetime.")
    candidate = raw.replace("Z", "+00:00")
    if len(candidate) == 16 and "T" in candidate:
        # Browser datetime-local commonly omits seconds: YYYY-MM-DDTHH:MM
        candidate = f"{candidate}:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid 'at' datetime. Use ISO format like 2026-03-14T12:00 or 2026-03-14T12:00:00+00:00.",
        ) from exc
    return _ensure_aware(parsed)

def _event_dict(e: AstronomicalEvent) -> dict:
    return {
        "id": str(e.id), "event_type": e.event_type,
        "body": e.body, "sign": e.sign,
        "at": e.at.isoformat(), "significance": e.significance,
        "ephemeris_data": e.ephemeris_data,
        "reading_status": e.reading_status,
        "reading_title": e.reading_title,
        "published_at": e.published_at.isoformat() if e.published_at else None,
    }

@router.get("/")
async def list_events(limit: int = Query(default=50), db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(AstronomicalEvent).order_by(AstronomicalEvent.at.desc()).limit(limit))
    return [_event_dict(e) for e in result.scalars().all()]

@router.get("/{event_id}")
async def get_event(event_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    e = await db.get(AstronomicalEvent, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_dict(e)

@router.post("/")
async def create_event(req: EventCreateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    e = AstronomicalEvent(
        event_type=req.event_type, body=req.body, sign=req.sign,
        at=_parse_event_datetime(req.at), significance=req.significance,
        ephemeris_data=req.ephemeris_data,
    )
    db.add(e)
    await db.flush()
    db.add(
        AuditLog(
            user_id=user.id,
            action="event.create",
            target_type="event",
            target_id=str(e.id),
            detail={
                "event_type": e.event_type,
                "significance": e.significance,
            },
        )
    )
    return {"id": str(e.id), "status": "created"}

@router.patch("/{event_id}")
async def update_event(event_id: UUID, req: EventUpdateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    e = await db.get(AstronomicalEvent, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    for field in ("event_type", "body", "sign", "significance", "ephemeris_data", "reading_status"):
        val = getattr(req, field, None)
        if val is not None:
            setattr(e, field, val)
    if req.at is not None:
        e.at = _parse_event_datetime(req.at)
    db.add(
        AuditLog(
            user_id=user.id,
            action="event.update",
            target_type="event",
            target_id=str(event_id),
            detail=req.model_dump(exclude_none=True),
        )
    )
    return {"status": "ok"}

@router.delete("/{event_id}")
async def delete_event(event_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    e = await db.get(AstronomicalEvent, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.delete(e)
    db.add(
        AuditLog(
            user_id=user.id,
            action="event.delete",
            target_type="event",
            target_id=str(event_id),
            detail={"event_type": e.event_type, "at": e.at.isoformat()},
        )
    )
    return {"status": "deleted"}

@router.post("/{event_id}/generate-reading")
async def generate_event_reading(event_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    e = await db.get(AstronomicalEvent, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    from pipeline.orchestrator import run_pipeline
    run_id = await run_pipeline(date_context=e.at.date(), trigger_source="manual_event")
    e.reading_status = "generated"
    e.run_id = run_id
    db.add(AuditLog(user_id=user.id, action="event.generate_reading", target_type="event", target_id=str(event_id)))
    return {"status": "triggered", "run_id": str(run_id)}
