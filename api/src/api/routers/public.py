"""Public API endpoints."""
from __future__ import annotations
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import Reading, AstronomicalEvent, PipelineRun
from api.dependencies import get_db

router = APIRouter()

@router.get("/reading/today")
async def get_today_reading(db: AsyncSession = Depends(get_db)):
    today = date.today()
    result = await db.execute(select(Reading).where(Reading.date_context == today, Reading.status == "published"))
    reading = result.scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="No published reading for today")
    content = reading.published_standard or reading.generated_standard
    return {"date_context": reading.date_context.isoformat(), "title": content.get("title",""), "body": content.get("body",""), "word_count": content.get("word_count",0), "published_at": reading.published_at.isoformat() if reading.published_at else None, "has_extended": bool(reading.published_extended or reading.generated_extended)}

@router.get("/reading/today/extended")
async def get_today_extended(db: AsyncSession = Depends(get_db)):
    today = date.today()
    result = await db.execute(select(Reading).where(Reading.date_context == today, Reading.status == "published"))
    reading = result.scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="No published reading for today")
    return {"date_context": reading.date_context.isoformat(), "extended": reading.published_extended or reading.generated_extended, "annotations": reading.published_annotations or reading.generated_annotations}

@router.get("/reading/{date_str}")
async def get_reading_by_date(date_str: str, db: AsyncSession = Depends(get_db)):
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    result = await db.execute(select(Reading).where(Reading.date_context == target, Reading.status == "published"))
    reading = result.scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="No published reading")
    content = reading.published_standard or reading.generated_standard
    return {"date_context": reading.date_context.isoformat(), "title": content.get("title",""), "body": content.get("body",""), "published_at": reading.published_at.isoformat() if reading.published_at else None}

@router.get("/ephemeris/today")
async def get_today_ephemeris(db: AsyncSession = Depends(get_db)):
    today = date.today()
    result = await db.execute(select(PipelineRun).where(PipelineRun.date_context == today, PipelineRun.status == "completed").order_by(PipelineRun.run_number.desc()))
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="No ephemeris data for today")
    return run.ephemeris_json

@router.get("/events")
async def get_events(limit: int = Query(default=10, le=50), db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = await db.execute(select(AstronomicalEvent).where(AstronomicalEvent.at >= now).order_by(AstronomicalEvent.at.asc()).limit(limit))
    return [{"id": str(e.id), "event_type": e.event_type, "body": e.body, "sign": e.sign, "at": e.at.isoformat(), "significance": e.significance} for e in result.scalars().all()]

@router.get("/archive")
async def get_archive(page: int = Query(default=1, ge=1), per_page: int = Query(default=30, le=100), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reading).where(Reading.status == "published").order_by(Reading.date_context.desc()).offset((page-1)*per_page).limit(per_page))
    return [{"date_context": r.date_context.isoformat(), "title": (r.published_standard or r.generated_standard or {}).get("title",""), "published_at": r.published_at.isoformat() if r.published_at else None} for r in result.scalars().all()]
