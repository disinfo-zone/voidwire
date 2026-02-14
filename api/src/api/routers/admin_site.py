"""Admin site configuration management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AdminUser, AuditLog

from api.dependencies import get_db, require_admin
from api.services.site_config import load_site_config, save_site_config

router = APIRouter()


class SiteConfigUpdateRequest(BaseModel):
    site_title: str | None = None
    tagline: str | None = None
    site_url: str | None = None
    timezone: str | None = None
    favicon_url: str | None = None
    meta_description: str | None = None
    og_image_url: str | None = None
    og_title_template: str | None = None
    twitter_handle: str | None = None
    tracking_head: str | None = None
    tracking_body: str | None = None


@router.get("/config")
async def get_site_config(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    return await load_site_config(db)


@router.put("/config")
async def update_site_config(
    req: SiteConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    current = await load_site_config(db)
    merged: dict[str, Any] = dict(current)
    merged.update(req.model_dump(exclude_none=True))
    updated = await save_site_config(db, merged)
    db.add(
        AuditLog(
            user_id=user.id,
            action="site.config.update",
            target_type="site",
            target_id="site.config",
            detail={"updated_fields": list(req.model_dump(exclude_none=True).keys())},
        )
    )
    return updated

