"""Admin events management."""
from __future__ import annotations
import asyncio
import logging
from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.database import get_session
from voidwire.models import AstronomicalEvent, AuditLog, AdminUser, PipelineRun, Reading
from api.dependencies import get_db, require_admin

router = APIRouter()
logger = logging.getLogger(__name__)

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


def _event_public_url(event_id: UUID) -> str:
    return f"/events/{event_id}"


async def _sync_event_reading_state(
    db: AsyncSession,
    event: AstronomicalEvent,
    *,
    run_id: UUID | None = None,
) -> None:
    if run_id is not None:
        event.run_id = run_id
    reading = None
    if event.run_id:
        result = await db.execute(select(Reading).where(Reading.run_id == event.run_id).limit(1))
        reading = result.scalars().first()

    if not reading:
        if event.run_id:
            event.reading_status = "pending"
        return

    content = reading.published_standard or reading.generated_standard or {}
    title = str(content.get("title", "")).strip()
    if title:
        event.reading_title = title

    if reading.status == "published":
        event.reading_status = "published"
        event.published_at = reading.published_at
        event.published_url = _event_public_url(event.id)
    else:
        event.reading_status = "generated"
        event.published_at = None
        event.published_url = None


async def _run_event_pipeline_background(event_id: UUID, date_context: date) -> None:
    from pipeline.orchestrator import run_pipeline

    try:
        run_id = await run_pipeline(
            date_context=date_context,
            trigger_source="manual_event",
            trigger_metadata={"source_event_id": str(event_id)},
        )
    except RuntimeError as exc:
        if "advisory lock" in str(exc).lower():
            logger.warning("Event pipeline run skipped due to lock conflict: %s", exc)
            return
        logger.exception("Event pipeline run failed: %s", exc)
        async with get_session() as db:
            event = await db.get(AstronomicalEvent, event_id)
            if event:
                event.reading_status = "skipped"
                event.published_at = None
                event.published_url = None
                await db.commit()
        return
    except Exception as exc:
        logger.exception("Event pipeline run failed: %s", exc)
        async with get_session() as db:
            event = await db.get(AstronomicalEvent, event_id)
            if event:
                event.reading_status = "skipped"
                event.published_at = None
                event.published_url = None
                await db.commit()
        return

    async with get_session() as db:
        event = await db.get(AstronomicalEvent, event_id)
        if not event:
            return
        await _sync_event_reading_state(db, event, run_id=run_id)
        await db.commit()


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
    running = await db.execute(
        select(PipelineRun).where(
            PipelineRun.date_context == e.at.date(),
            PipelineRun.status == "running",
        )
    )
    if running.scalars().first() is not None:
        raise HTTPException(status_code=409, detail="A pipeline run for this event date is already in progress.")

    from api.routers.admin_pipeline import _is_pipeline_lock_available

    if not await _is_pipeline_lock_available(db, e.at.date()):
        raise HTTPException(status_code=409, detail="A pipeline run for this event date is already in progress.")

    e.reading_status = "pending"
    e.published_at = None
    e.published_url = None
    db.add(
        AuditLog(
            user_id=user.id,
            action="event.generate_reading",
            target_type="event",
            target_id=str(event_id),
            detail={"date_context": e.at.date().isoformat(), "mode": "background"},
        )
    )
    asyncio.create_task(_run_event_pipeline_background(event_id=e.id, date_context=e.at.date()))
    return {
        "status": "started",
        "mode": "background",
        "date_context": e.at.date().isoformat(),
    }
