"""Admin pipeline management."""
from __future__ import annotations
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import PipelineRun, AdminUser
from voidwire.schemas.pipeline import RegenerationMode
from api.dependencies import get_db, require_admin

router = APIRouter()

class TriggerRequest(BaseModel):
    regeneration_mode: str | None = None
    date_context: str | None = None
    parent_run_id: str | None = None

def _run_summary(r: PipelineRun) -> dict:
    return {
        "id": str(r.id), "date_context": r.date_context.isoformat(),
        "run_number": r.run_number, "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "ended_at": r.ended_at.isoformat() if r.ended_at else None,
        "regeneration_mode": r.regeneration_mode,
        "error_detail": r.error_detail,
    }

@router.get("/runs")
async def list_runs(page: int = Query(default=1, ge=1), db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc()).offset((page-1)*20).limit(20))
    return [_run_summary(r) for r in result.scalars().all()]

@router.get("/runs/{run_id}")
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        **_run_summary(run),
        "seed": run.seed, "code_version": run.code_version,
        "model_config_json": run.model_config_json,
        "template_versions": run.template_versions,
        "selected_signals": run.selected_signals,
        "thread_snapshot": run.thread_snapshot,
        "interpretive_plan": run.interpretive_plan,
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
    }

@router.get("/runs/{run_id}/artifacts")
async def get_run_artifacts(run_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "ephemeris_json": run.ephemeris_json,
        "distilled_signals": run.distilled_signals,
        "selected_signals": run.selected_signals,
        "thread_snapshot": run.thread_snapshot,
        "prompt_payloads": run.prompt_payloads,
        "interpretive_plan": run.interpretive_plan,
        "generated_output": run.generated_output,
        "model_config_json": run.model_config_json,
        "ephemeris_hash": run.ephemeris_hash,
        "distillation_hash": run.distillation_hash,
        "selection_hash": run.selection_hash,
    }

@router.post("/trigger")
async def trigger_pipeline(req: TriggerRequest = None, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    from pipeline.orchestrator import run_pipeline
    if req is None:
        req = TriggerRequest()
    dc = None
    if req.date_context:
        dc = date.fromisoformat(req.date_context)
    mode = None
    if req.regeneration_mode:
        mode = RegenerationMode(req.regeneration_mode)
    parent = UUID(req.parent_run_id) if req.parent_run_id else None
    run_id = await run_pipeline(date_context=dc, regeneration_mode=mode, parent_run_id=parent)
    return {"status": "triggered", "run_id": str(run_id)}
