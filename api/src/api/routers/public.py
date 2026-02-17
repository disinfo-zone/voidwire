"""Public API endpoints."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AstronomicalEvent, PipelineRun, Reading

from api.dependencies import get_db
from api.services.content_pages import get_content_page
from api.services.site_config import load_site_asset_content, load_site_config

router = APIRouter()
EVENT_TRIGGER_SOURCE = "manual_event"


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


def _trigger_source_for_run(run: PipelineRun | None) -> str:
    if run is None:
        return "scheduler"
    artifacts = run.reused_artifacts if isinstance(run.reused_artifacts, dict) else {}
    source = str(artifacts.get("trigger_source", "scheduler")).strip().lower()
    return source or "scheduler"


def _is_event_reading_run(run: PipelineRun | None) -> bool:
    return _trigger_source_for_run(run) == EVENT_TRIGGER_SOURCE


async def _today_for_site_timezone(db: AsyncSession) -> date:
    config = await load_site_config(db)
    tz_name = str(config.get("timezone", "UTC")).strip() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = UTC
    return datetime.now(tz).date()


async def _get_primary_public_reading_for_date(db: AsyncSession, target: date) -> Reading | None:
    result = await db.execute(
        select(Reading, PipelineRun)
        .join(PipelineRun, PipelineRun.id == Reading.run_id, isouter=True)
        .where(Reading.date_context == target, Reading.status == "published")
        .order_by(Reading.published_at.desc(), Reading.created_at.desc())
    )
    for reading, run in result.all():
        if not _is_event_reading_run(run):
            return reading
    return None


@router.get("/reading/today")
async def get_today_reading(db: AsyncSession = Depends(get_db)):
    today = await _today_for_site_timezone(db)
    reading = await _get_primary_public_reading_for_date(db, today)
    if not reading:
        raise HTTPException(status_code=404, detail="No published reading for today")
    return _reading_payload(reading)


@router.get("/reading/today/extended")
async def get_today_extended(db: AsyncSession = Depends(get_db)):
    today = await _today_for_site_timezone(db)
    reading = await _get_primary_public_reading_for_date(db, today)
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
    reading = await _get_primary_public_reading_for_date(db, target)
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


@router.get("/site/assets/{kind}")
async def get_site_asset(kind: str, db: AsyncSession = Depends(get_db)):
    try:
        asset = await load_site_asset_content(db, kind)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Site asset not found") from exc
    if asset is None:
        raise HTTPException(status_code=404, detail="Site asset not found")
    content, content_type = asset
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/ephemeris/today")
async def get_today_ephemeris(db: AsyncSession = Depends(get_db)):
    today = await _today_for_site_timezone(db)
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.date_context == today, PipelineRun.status == "completed")
        .order_by(PipelineRun.run_number.desc())
    )
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="No ephemeris data for today")
    return run.ephemeris_json


@router.get("/ephemeris/today/weather")
async def get_today_weather(db: AsyncSession = Depends(get_db)):
    from api.services.weather_service import get_or_generate_weather

    result = await get_or_generate_weather(db)
    if not result:
        raise HTTPException(status_code=404, detail="Weather descriptions unavailable")
    return result


@router.get("/ephemeris/{date_str}")
async def get_ephemeris_by_date(date_str: str, db: AsyncSession = Depends(get_db)):
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.date_context == target, PipelineRun.status == "completed")
        .order_by(PipelineRun.run_number.desc())
    )
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="No ephemeris data for this date")
    return run.ephemeris_json


@router.get("/events")
async def get_events(limit: int = Query(default=10, le=50), db: AsyncSession = Depends(get_db)):
    now = datetime.now(UTC)
    result = await db.execute(
        select(AstronomicalEvent)
        .where(AstronomicalEvent.at >= now)
        .order_by(AstronomicalEvent.at.asc())
        .limit(limit)
    )
    events = result.scalars().all()
    run_ids = [e.run_id for e in events if e.run_id]
    reading_by_run: dict[UUID, Reading] = {}
    if run_ids:
        reading_result = await db.execute(select(Reading).where(Reading.run_id.in_(run_ids)))
        for reading in reading_result.scalars().all():
            reading_by_run[reading.run_id] = reading
    payload = []
    for event in events:
        reading = reading_by_run.get(event.run_id) if event.run_id else None
        content = (
            (reading.published_standard if reading else None)
            or (reading.generated_standard if reading else None)
            or {}
        )
        payload.append(
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "body": event.body,
                "sign": event.sign,
                "at": event.at.isoformat(),
                "significance": event.significance,
                "reading_status": reading.status if reading else event.reading_status,
                "reading_available": reading is not None,
                "reading_title": str(content.get("title", "")).strip()
                if content
                else (event.reading_title or ""),
                "reading_url": f"/events/{event.id}" if reading is not None else None,
            }
        )
    return payload


@router.get("/events/{event_id}")
async def get_event_with_reading(event_id: UUID, db: AsyncSession = Depends(get_db)):
    event = await db.get(AstronomicalEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    reading = None
    if event.run_id:
        result = await db.execute(select(Reading).where(Reading.run_id == event.run_id).limit(1))
        reading = result.scalars().first()

    payload = {
        "id": str(event.id),
        "event_type": event.event_type,
        "body": event.body,
        "sign": event.sign,
        "at": event.at.isoformat(),
        "significance": event.significance,
        "reading_status": event.reading_status,
        "reading_title": event.reading_title,
        "reading_available": reading is not None,
        "reading_url": f"/events/{event.id}" if reading is not None else None,
        "reading": None,
    }
    if reading is not None:
        reading_payload = _reading_payload(reading)
        reading_payload["status"] = reading.status
        payload["reading"] = reading_payload
        payload["reading_status"] = reading.status
        content = reading.published_standard or reading.generated_standard or {}
        if str(content.get("title", "")).strip():
            payload["reading_title"] = str(content.get("title", "")).strip()
    return payload


@router.get("/archive")
async def get_archive(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reading, PipelineRun)
        .join(PipelineRun, PipelineRun.id == Reading.run_id, isouter=True)
        .where(Reading.status == "published")
        .order_by(Reading.date_context.desc(), Reading.published_at.desc())
    )
    filtered = [(reading, run) for reading, run in result.all() if not _is_event_reading_run(run)]
    start = (page - 1) * per_page
    end = start + per_page
    window = filtered[start:end]
    return [
        {
            "date_context": reading.date_context.isoformat(),
            "title": (reading.published_standard or reading.generated_standard or {}).get(
                "title", ""
            ),
            "published_at": reading.published_at.isoformat() if reading.published_at else None,
        }
        for reading, _ in window
    ]
