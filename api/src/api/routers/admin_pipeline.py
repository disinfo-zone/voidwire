"""Admin pipeline management."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import PipelineRun, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

@router.get("/runs")
async def list_runs(page: int = Query(default=1, ge=1), db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc()).offset((page-1)*20).limit(20))
    return [{"id": str(r.id), "date_context": r.date_context.isoformat(), "run_number": r.run_number, "status": r.status, "started_at": r.started_at.isoformat() if r.started_at else None} for r in result.scalars().all()]

@router.get("/runs/{run_id}")
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"id": str(run.id), "date_context": run.date_context.isoformat(), "status": run.status, "seed": run.seed, "selected_signals": run.selected_signals, "thread_snapshot": run.thread_snapshot, "interpretive_plan": run.interpretive_plan}

@router.post("/trigger")
async def trigger_pipeline(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    from pipeline.orchestrator import run_pipeline
    run_id = await run_pipeline()
    return {"status": "triggered", "run_id": str(run_id)}
