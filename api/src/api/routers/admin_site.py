"""Admin site configuration management."""

from __future__ import annotations

import base64
import binascii
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AdminUser, AuditLog

from api.dependencies import get_db, require_admin
from api.services.email_template_service import (
    load_email_templates,
    load_rendered_email_template,
    save_email_templates,
)
from api.services.email_service import (
    load_smtp_config,
    save_smtp_config,
    send_transactional_email,
)
from api.services.oauth_config import load_oauth_config, save_oauth_config
from api.services.site_config import load_site_config, save_site_asset, save_site_config
from api.services.stripe_config import load_stripe_config, resolve_stripe_runtime_config, save_stripe_config
from api.services.stripe_service import run_stripe_connectivity_check

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


class SiteAssetUploadRequest(BaseModel):
    kind: Literal["favicon", "twittercard"]
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=120)
    data_base64: str = Field(min_length=8, max_length=8_000_000)


class SMTPConfigUpdateRequest(BaseModel):
    enabled: bool | None = None
    provider: Literal["smtp", "resend"] | None = None
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=320)
    password: str | None = Field(default=None, max_length=512)
    resend_api_key: str | None = Field(default=None, max_length=4096)
    resend_api_base_url: str | None = Field(default=None, max_length=512)
    from_email: str | None = Field(default=None, max_length=320)
    from_name: str | None = Field(default=None, max_length=160)
    reply_to: str | None = Field(default=None, max_length=320)
    use_ssl: bool | None = None
    use_starttls: bool | None = None


class SMTPTestRequest(BaseModel):
    to_email: str = Field(min_length=3, max_length=320)


class EmailTemplateContentUpdateRequest(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=5000)
    text_body: str | None = Field(default=None, min_length=1, max_length=50000)
    html_body: str | None = Field(default=None, min_length=1, max_length=100000)


class EmailTemplatesUpdateRequest(BaseModel):
    verification: EmailTemplateContentUpdateRequest | None = None
    password_reset: EmailTemplateContentUpdateRequest | None = None
    test_email: EmailTemplateContentUpdateRequest | None = None


class OAuthGoogleConfigUpdateRequest(BaseModel):
    enabled: bool | None = None
    client_id: str | None = Field(default=None, max_length=320)
    client_secret: str | None = Field(default=None, max_length=4096)


class OAuthAppleConfigUpdateRequest(BaseModel):
    enabled: bool | None = None
    client_id: str | None = Field(default=None, max_length=320)
    team_id: str | None = Field(default=None, max_length=120)
    key_id: str | None = Field(default=None, max_length=120)
    private_key: str | None = Field(default=None, max_length=8192)


class OAuthConfigUpdateRequest(BaseModel):
    google: OAuthGoogleConfigUpdateRequest | None = None
    apple: OAuthAppleConfigUpdateRequest | None = None


class StripeConfigUpdateRequest(BaseModel):
    enabled: bool | None = None
    publishable_key: str | None = Field(default=None, max_length=320)
    secret_key: str | None = Field(default=None, max_length=320)
    webhook_secret: str | None = Field(default=None, max_length=320)


def _decode_base64_payload(raw: str) -> bytes:
    payload = str(raw or "").strip()
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")
    if not payload:
        raise ValueError("Image payload is empty")
    try:
        return base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Image payload is not valid base64") from exc


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
    subject, text_body, html_body = await load_rendered_email_template(
        db,
        template_key="test_email",
        context={"site_name": "Voidwire"},
    )
    try:
        delivered = await send_transactional_email(
            db,
            to_email=req.to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            raise_on_error=True,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not delivered:
        raise HTTPException(status_code=400, detail="Test email failed to send")
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


@router.get("/email/templates")
async def get_email_templates(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    return await load_email_templates(db)


@router.put("/email/templates")
async def update_email_templates(
    req: EmailTemplatesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    payload = req.model_dump(exclude_none=True)
    updated = await save_email_templates(db, payload)
    db.add(
        AuditLog(
            user_id=user.id,
            action="email.templates.update",
            target_type="site",
            target_id="email.templates",
            detail={"updated_fields": list(payload.keys())},
        )
    )
    return updated


@router.get("/auth/oauth")
async def get_oauth_config(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    return await load_oauth_config(db)


@router.put("/auth/oauth")
async def update_oauth_config(
    req: OAuthConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    payload = req.model_dump(exclude_none=True)
    updated = await save_oauth_config(db, payload)
    db.add(
        AuditLog(
            user_id=user.id,
            action="auth.oauth.update",
            target_type="site",
            target_id="auth.oauth",
            detail={
                "updated_fields": list(payload.keys()),
                "google_enabled": bool(updated.get("google", {}).get("enabled")),
                "apple_enabled": bool(updated.get("apple", {}).get("enabled")),
            },
        )
    )
    return updated


@router.get("/billing/stripe")
async def get_stripe_config(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    return await load_stripe_config(db)


@router.put("/billing/stripe")
async def update_stripe_config(
    req: StripeConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    payload = req.model_dump(exclude_none=True)
    updated = await save_stripe_config(db, payload)
    db.add(
        AuditLog(
            user_id=user.id,
            action="billing.stripe.update",
            target_type="site",
            target_id="billing.stripe",
            detail={
                "updated_fields": list(payload.keys()),
                "enabled": bool(updated.get("enabled")),
                "is_configured": bool(updated.get("is_configured")),
            },
        )
    )
    return updated


@router.post("/billing/stripe/test")
async def test_stripe_config(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    runtime = await resolve_stripe_runtime_config(db)
    result = run_stripe_connectivity_check(
        secret_key=str(runtime.get("secret_key") or "").strip(),
        publishable_key=str(runtime.get("publishable_key") or "").strip(),
        webhook_secret=str(runtime.get("webhook_secret") or "").strip(),
        price_limit=5,
    )
    db.add(
        AuditLog(
            user_id=user.id,
            action="billing.stripe.test",
            target_type="site",
            target_id="billing.stripe",
            detail={
                "status": result.get("status"),
                "warnings": result.get("warnings", []),
                "active_price_count": result.get("active_price_count", 0),
            },
        )
    )
    return result


@router.post("/assets")
async def upload_site_asset_endpoint(
    req: SiteAssetUploadRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    try:
        raw_bytes = _decode_base64_payload(req.data_base64)
        asset = await save_site_asset(
            db,
            kind=req.kind,
            filename=req.filename,
            content_type=req.content_type,
            content_bytes=raw_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    current_config = await load_site_config(db)
    merged: dict[str, Any] = dict(current_config)
    if req.kind == "favicon":
        merged["favicon_url"] = asset["url"]
        configured_url = merged["favicon_url"]
    else:
        merged["og_image_url"] = asset["url"]
        configured_url = merged["og_image_url"]
    await save_site_config(db, merged)

    db.add(
        AuditLog(
            user_id=user.id,
            action="site.asset.upload",
            target_type="site",
            target_id=f"site.asset.{req.kind}",
            detail={
                "kind": req.kind,
                "filename": asset.get("filename"),
                "content_type": asset.get("content_type"),
                "size_bytes": asset.get("size_bytes"),
                "configured_url": configured_url,
            },
        )
    )
    return {
        "status": "ok",
        "kind": req.kind,
        "url": configured_url,
        "asset": asset,
    }
