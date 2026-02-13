"""Admin settings."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import SiteSetting, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

class SettingRequest(BaseModel):
    key: str
    value: dict
    category: str = "general"

@router.get("/")
async def list_settings(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(SiteSetting))
    return [{"key": s.key, "value": s.value, "category": s.category} for s in result.scalars().all()]

@router.put("/")
async def update_setting(req: SettingRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    setting = await db.get(SiteSetting, req.key)
    if setting:
        setting.value = req.value
    else:
        db.add(SiteSetting(key=req.key, value=req.value, category=req.category))
    return {"status": "ok"}
