"""Admin settings."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import SiteSetting, AdminUser, AuditLog
from voidwire.services.pipeline_settings import pipeline_settings_schema, load_pipeline_settings
from api.dependencies import get_db, require_admin

router = APIRouter()

class SettingRequest(BaseModel):
    key: str
    value: dict
    category: str = "general"

@router.get("/")
async def list_settings(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    query = select(SiteSetting)
    if category:
        query = query.where(SiteSetting.category == category)
    result = await db.execute(query)
    return [
        {"key": s.key, "value": s.value, "category": s.category, "description": s.description, "updated_at": s.updated_at.isoformat() if s.updated_at else None}
        for s in result.scalars().all()
    ]

@router.get("/schema/pipeline")
async def get_pipeline_schema(user: AdminUser = Depends(require_admin)):
    return pipeline_settings_schema()

@router.get("/defaults/pipeline")
async def get_pipeline_defaults(user: AdminUser = Depends(require_admin)):
    from voidwire.services.pipeline_settings import PipelineSettings
    return PipelineSettings().model_dump()

@router.get("/effective/pipeline")
async def get_effective_pipeline_settings(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    ps = await load_pipeline_settings(db)
    return ps.model_dump()

@router.get("/{key:path}")
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    setting = await db.get(SiteSetting, key)
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"key": setting.key, "value": setting.value, "category": setting.category, "description": setting.description, "updated_at": setting.updated_at.isoformat() if setting.updated_at else None}

@router.put("/")
async def update_setting(
    req: SettingRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    setting = await db.get(SiteSetting, req.key)
    if setting:
        setting.value = req.value
        setting.updated_at = datetime.now(timezone.utc)
    else:
        db.add(SiteSetting(key=req.key, value=req.value, category=req.category))
    db.add(
        AuditLog(
            user_id=user.id,
            action="setting.update",
            target_type="setting",
            target_id=req.key,
            detail={"category": req.category, "value": req.value},
        )
    )
    return {"status": "ok"}

@router.delete("/{key:path}")
async def delete_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    setting = await db.get(SiteSetting, key)
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    await db.delete(setting)
    db.add(
        AuditLog(
            user_id=user.id,
            action="setting.delete",
            target_type="setting",
            target_id=key,
        )
    )
    return {"status": "deleted"}

@router.post("/reset-category/{category}")
async def reset_category(
    category: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    result = await db.execute(
        delete(SiteSetting).where(SiteSetting.category == category)
    )
    db.add(
        AuditLog(
            user_id=user.id,
            action="setting.reset_category",
            target_type="setting",
            target_id=category,
            detail={"deleted_count": result.rowcount},
        )
    )
    return {"status": "ok", "deleted_count": result.rowcount}
