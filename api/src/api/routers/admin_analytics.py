"""Admin analytics."""
from __future__ import annotations
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AnalyticsEvent, PipelineRun, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

@router.get("/events")
async def get_analytics(days: int = Query(default=30), db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(select(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id)).where(AnalyticsEvent.created_at >= cutoff).group_by(AnalyticsEvent.event_type))
    return [{"event_type": r[0], "count": r[1]} for r in result.all()]

@router.get("/pipeline-health")
async def get_pipeline_health(days: int = Query(default=30), db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(select(PipelineRun.status, func.count(PipelineRun.id)).where(PipelineRun.date_context >= cutoff).group_by(PipelineRun.status))
    return [{"status": r[0], "count": r[1]} for r in result.all()]
