"""Public API endpoints."""
from __future__ import annotations
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import Reading, AstronomicalEvent, PipelineRun
from api.dependencies import get_db
from api.services.content_pages import get_content_page
from api.services.site_config import load_site_config

router = APIRouter()


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_extended_payload(reading: Reading) -> dict:
    source = reading.published_extended
    if not isinstance(source, dict) or not source:
        source = reading.generated_extended if isinstance(reading.generated_extended, dict) else {}

    sections_raw = source.get("sections") if isinstance(source, dict) else []
    sections: list[dict] = []
    if isinstance(sections_raw, list):
        for item in sections_raw:
            if not isinstance(item, dict):
                continue
            heading = str(item.get("heading", "")).strip()
            body = str(item.get("body", "")).strip()
            if heading or body:
                sections.append({"heading": heading, "body": body})

    return {
        "title": str(source.get("title", "")).strip(),
        "subtitle": str(source.get("subtitle", "")).strip(),
        "sections": sections,
        "word_count": max(_safe_int(source.get("word_count"), 0), 0),
    }


def _has_extended(extended: dict) -> bool:
    if not isinstance(extended, dict):
        return False
    if extended.get("sections"):
        return True
    if str(extended.get("title", "")).strip():
        return True
    if str(extended.get("subtitle", "")).strip():
        return True
    return _safe_int(extended.get("word_count"), 0) > 0


def _reading_payload(reading: Reading) -> dict:
    content = reading.published_standard or reading.generated_standard or {}
    extended = _normalize_extended_payload(reading)
    return {
        "date_context": reading.date_context.isoformat(),
        "title": content.get("title", ""),
        "body": content.get("body", ""),
        "word_count": content.get("word_count", 0),
        "published_at": reading.published_at.isoformat() if reading.published_at else None,
        "has_extended": _has_extended(extended),
        "extended": extended,
        "annotations": reading.published_annotations or reading.generated_annotations or [],
    }

@router.get("/reading/today")
async def get_today_reading(db: AsyncSession = Depends(get_db)):
    today = date.today()
    result = await db.execute(select(Reading).where(Reading.date_context == today, Reading.status == "published"))
    reading = result.scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="No published reading for today")
    return _reading_payload(reading)

@router.get("/reading/today/extended")
async def get_today_extended(db: AsyncSession = Depends(get_db)):
    today = date.today()
    result = await db.execute(select(Reading).where(Reading.date_context == today, Reading.status == "published"))
    reading = result.scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="No published reading for today")
    return {
        "date_context": reading.date_context.isoformat(),
        "extended": _normalize_extended_payload(reading),
        "annotations": reading.published_annotations or reading.generated_annotations or [],
    }

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
    return _reading_payload(reading)


@router.get("/content/{slug}")
async def get_content_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    try:
        return await get_content_page(db, slug.strip().lower())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Content page not found") from exc


@router.get("/site/config")
async def get_public_site_config(db: AsyncSession = Depends(get_db)):
    cfg = await load_site_config(db)
    return {
        "site_title": cfg.get("site_title", "VOIDWIRE"),
        "tagline": cfg.get("tagline", ""),
        "site_url": cfg.get("site_url", ""),
        "timezone": cfg.get("timezone", "UTC"),
        "favicon_url": cfg.get("favicon_url", ""),
        "meta_description": cfg.get("meta_description", ""),
        "og_image_url": cfg.get("og_image_url", ""),
        "og_title_template": cfg.get("og_title_template", "{{title}} | {{site_title}}"),
        "twitter_handle": cfg.get("twitter_handle", ""),
        "tracking_head": cfg.get("tracking_head", ""),
        "tracking_body": cfg.get("tracking_body", ""),
    }

@router.get("/ephemeris/today")
async def get_today_ephemeris(db: AsyncSession = Depends(get_db)):
    today = date.today()
    result = await db.execute(select(PipelineRun).where(PipelineRun.date_context == today, PipelineRun.status == "completed").order_by(PipelineRun.run_number.desc()))
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="No ephemeris data for today")
    return run.ephemeris_json

@router.get("/ephemeris/{date_str}")
async def get_ephemeris_by_date(date_str: str, db: AsyncSession = Depends(get_db)):
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    result = await db.execute(select(PipelineRun).where(PipelineRun.date_context == target, PipelineRun.status == "completed").order_by(PipelineRun.run_number.desc()))
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="No ephemeris data for this date")
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
