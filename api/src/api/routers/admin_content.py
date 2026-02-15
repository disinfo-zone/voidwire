"""Admin content page management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AdminUser, AuditLog

from api.dependencies import get_db, require_admin
from api.services.content_pages import get_content_page, list_content_pages, save_content_page

router = APIRouter()


class ContentSectionInput(BaseModel):
    heading: str = ""
    body: str = ""


class ContentPageUpdateRequest(BaseModel):
    title: str = ""
    sections: list[ContentSectionInput] = []


@router.get("/pages")
async def list_pages(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    return await list_content_pages(db)


@router.get("/pages/{slug}")
async def get_page(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    try:
        return await get_content_page(db, slug.strip().lower())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Content page not found") from exc


@router.put("/pages/{slug}")
async def update_page(
    slug: str,
    req: ContentPageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    target_slug = slug.strip().lower()
    payload: dict[str, Any] = {
        "title": req.title,
        "sections": [section.model_dump() for section in req.sections],
    }
    try:
        page = await save_content_page(db, target_slug, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Content page not found") from exc

    db.add(
        AuditLog(
            user_id=user.id,
            action="content.page.update",
            target_type="content",
            target_id=target_slug,
            detail={
                "slug": target_slug,
                "title": page.get("title", ""),
                "sections_count": len(page.get("sections", [])),
            },
        )
    )
    return page
