"""Admin readings management."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import Reading, PipelineRun, CulturalSignal, AuditLog, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()
logger = logging.getLogger(__name__)

class ReadingUpdateRequest(BaseModel):
    status: str | None = None
    published_standard: dict | None = None
    editorial_notes: str | None = None

class ReadingContentUpdateRequest(BaseModel):
    published_standard: dict | None = None
    published_extended: dict | None = None
    published_annotations: list | None = None
    editorial_notes: str | None = None

class RegenerateRequest(BaseModel):
    mode: str = "prose_only"  # prose_only | reselect | full_rerun
    wait_for_completion: bool = False


def _load_pipeline_runner():
    try:
        from pipeline.orchestrator import run_pipeline
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Pipeline package is unavailable in API container. Rebuild API image.",
        ) from exc
    return run_pipeline


async def _run_pipeline_background(
    run_pipeline,
    *,
    date_context,
    regeneration_mode,
    parent_run_id,
    trigger_source: str,
) -> None:
    try:
        run_id = await run_pipeline(
            date_context=date_context,
            regeneration_mode=regeneration_mode,
            parent_run_id=parent_run_id,
            trigger_source=trigger_source,
        )
        logger.info("Background reading regeneration completed: %s", run_id)
    except RuntimeError as exc:
        if "advisory lock" in str(exc).lower():
            logger.warning("Reading regeneration skipped due to lock conflict: %s", exc)
            return
        logger.exception("Background reading regeneration failed: %s", exc)
    except Exception as exc:
        logger.exception("Background reading regeneration failed: %s", exc)

def _reading_dict(r: Reading) -> dict:
    return {
        "id": str(r.id), "run_id": str(r.run_id),
        "date_context": r.date_context.isoformat(), "status": r.status,
        "generated_standard": r.generated_standard,
        "generated_extended": r.generated_extended,
        "generated_annotations": r.generated_annotations,
        "published_standard": r.published_standard,
        "published_extended": r.published_extended,
        "published_annotations": r.published_annotations,
        "editorial_diff": r.editorial_diff,
        "editorial_notes": r.editorial_notes,
        "published_at": r.published_at.isoformat() if r.published_at else None,
    }

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
    return _reading_dict(reading)

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

@router.patch("/{reading_id}/content")
async def update_reading_content(reading_id: UUID, req: ReadingContentUpdateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    reading = await db.get(Reading, reading_id)
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    if req.published_standard is not None:
        reading.published_standard = req.published_standard
    if req.published_extended is not None:
        reading.published_extended = req.published_extended
    if req.published_annotations is not None:
        reading.published_annotations = req.published_annotations
    if req.editorial_notes is not None:
        reading.editorial_notes = req.editorial_notes
    # Compute editorial diff
    diff = {}
    if reading.published_standard and reading.generated_standard:
        if reading.published_standard != reading.generated_standard:
            diff["standard"] = {"generated_title": reading.generated_standard.get("title"), "published_title": reading.published_standard.get("title"), "body_changed": reading.published_standard.get("body") != reading.generated_standard.get("body")}
    if reading.published_extended and reading.generated_extended:
        if reading.published_extended != reading.generated_extended:
            diff["extended"] = True
    reading.editorial_diff = diff if diff else None
    reading.updated_at = datetime.now(timezone.utc)
    db.add(AuditLog(user_id=user.id, action="reading.content_edit", target_type="reading", target_id=str(reading_id)))
    return {"status": "ok", "editorial_diff": diff}

@router.get("/{reading_id}/diff")
async def get_reading_diff(reading_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    reading = await db.get(Reading, reading_id)
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    return {
        "generated_standard": reading.generated_standard,
        "published_standard": reading.published_standard,
        "generated_extended": reading.generated_extended,
        "published_extended": reading.published_extended,
        "editorial_diff": reading.editorial_diff,
    }

@router.post("/{reading_id}/regenerate")
async def regenerate_reading(reading_id: UUID, req: RegenerateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    reading = await db.get(Reading, reading_id)
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    from voidwire.schemas.pipeline import RegenerationMode
    from api.routers.admin_pipeline import _is_pipeline_lock_available

    run_pipeline = _load_pipeline_runner()
    mode_map = {"prose_only": RegenerationMode.PROSE_ONLY, "reselect": RegenerationMode.RESELECT, "full_rerun": RegenerationMode.FULL_RERUN}
    mode = mode_map.get(req.mode, RegenerationMode.PROSE_ONLY)

    running = await db.execute(
        select(PipelineRun).where(
            PipelineRun.date_context == reading.date_context,
            PipelineRun.status == "running",
        )
    )
    if running.scalars().first() is not None:
        raise HTTPException(status_code=409, detail="A pipeline run for this date is already in progress.")
    if not await _is_pipeline_lock_available(db, reading.date_context):
        raise HTTPException(status_code=409, detail="A pipeline run for this date is already in progress.")

    db.add(
        AuditLog(
            user_id=user.id,
            action=f"reading.regenerate.{req.mode}",
            target_type="reading",
            target_id=str(reading_id),
            detail={
                "mode": mode.value,
                "date_context": reading.date_context.isoformat(),
                "parent_run_id": str(reading.run_id),
                "wait_for_completion": bool(req.wait_for_completion),
            },
        )
    )

    if not req.wait_for_completion:
        asyncio.create_task(
            _run_pipeline_background(
                run_pipeline,
                date_context=reading.date_context,
                regeneration_mode=mode,
                parent_run_id=reading.run_id,
                trigger_source="manual_regenerate",
            )
        )
        return {
            "status": "started",
            "mode": "background",
            "date_context": reading.date_context.isoformat(),
            "regeneration_mode": mode.value,
        }

    try:
        run_id = await run_pipeline(
            date_context=reading.date_context,
            regeneration_mode=mode,
            parent_run_id=reading.run_id,
            trigger_source="manual_regenerate",
        )
    except RuntimeError as exc:
        if "advisory lock" in str(exc).lower():
            raise HTTPException(status_code=409, detail="A pipeline run for this date is already in progress.") from exc
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {exc}") from exc
    return {"status": "triggered", "run_id": str(run_id)}

@router.get("/{reading_id}/signals")
async def get_reading_signals(reading_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    reading = await db.get(Reading, reading_id)
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    result = await db.execute(
        select(CulturalSignal).where(
            CulturalSignal.run_id == reading.run_id,
            CulturalSignal.was_selected == True,
        )
    )
    signals = result.scalars().all()
    return [
        {
            "id": s.id, "summary": s.summary, "domain": s.domain,
            "intensity": s.intensity, "directionality": s.directionality,
            "entities": s.entities, "was_wild_card": s.was_wild_card,
            "selection_weight": s.selection_weight,
        }
        for s in signals
    ]
