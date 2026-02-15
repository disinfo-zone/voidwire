"""Admin site configuration management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AdminUser, AuditLog

from api.dependencies import get_db, require_admin
from api.services.email_service import (
    load_smtp_config,
    save_smtp_config,
    send_transactional_email,
)
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


class SMTPConfigUpdateRequest(BaseModel):
    enabled: bool | None = None
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=320)
    password: str | None = Field(default=None, max_length=512)
    from_email: str | None = Field(default=None, max_length=320)
    from_name: str | None = Field(default=None, max_length=160)
    reply_to: str | None = Field(default=None, max_length=320)
    use_ssl: bool | None = None
    use_starttls: bool | None = None


class SMTPTestRequest(BaseModel):
    to_email: str = Field(min_length=3, max_length=320)


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


@router.get("/email/smtp")
async def get_smtp_config(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    return await load_smtp_config(db)


@router.put("/email/smtp")
async def update_smtp_config(
    req: SMTPConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    updated = await save_smtp_config(db, req.model_dump(exclude_none=True))
    db.add(
        AuditLog(
            user_id=user.id,
            action="email.smtp.update",
            target_type="site",
            target_id="email.smtp",
            detail={"updated_fields": list(req.model_dump(exclude_none=True).keys())},
        )
    )
    return updated


@router.post("/email/smtp/test")
async def send_test_email(
    req: SMTPTestRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    delivered = await send_transactional_email(
        db,
        to_email=req.to_email,
        subject="Voidwire SMTP Test",
        text_body=(
            "This is a test email from Voidwire.\n\n"
            "If you received this message, SMTP settings are working."
        ),
        html_body=(
            "<p>This is a test email from <strong>Voidwire</strong>.</p>"
            "<p>If you received this message, SMTP settings are working.</p>"
        ),
    )
    if not delivered:
        raise HTTPException(status_code=400, detail="SMTP test email failed to send")
    db.add(
        AuditLog(
            user_id=user.id,
            action="email.smtp.test_send",
            target_type="site",
            target_id="email.smtp",
            detail={"to_email": req.to_email},
        )
    )
    return {"status": "sent"}
