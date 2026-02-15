"""Admin prompt template management."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import PromptTemplate, AdminUser, AuditLog
from api.dependencies import get_db, require_admin
from api.services.template_defaults import ensure_starter_prompt_template

router = APIRouter()

class TemplateCreateRequest(BaseModel):
    template_name: str
    content: str
    variables_used: list[str] = []
    tone_parameters: dict | None = None
    notes: str | None = None

def _template_dict(t: PromptTemplate) -> dict:
    return {
        "id": str(t.id), "template_name": t.template_name,
        "version": t.version, "is_active": t.is_active,
        "content": t.content, "variables_used": t.variables_used,
        "tone_parameters": t.tone_parameters, "notes": t.notes,
        "author": t.author,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }

@router.get("/")
async def list_templates(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    await ensure_starter_prompt_template(db)
    result = await db.execute(
        select(PromptTemplate)
        .where(PromptTemplate.is_active == True)
        .order_by(PromptTemplate.template_name.asc())
    )
    return [_template_dict(t) for t in result.scalars().all()]

@router.get("/{template_id}")
async def get_template(template_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    t = await db.get(PromptTemplate, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_dict(t)

@router.get("/versions/{template_name}")
async def get_template_versions(template_name: str, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(
        select(PromptTemplate)
        .where(PromptTemplate.template_name == template_name)
        .order_by(PromptTemplate.version.desc())
    )
    return [_template_dict(t) for t in result.scalars().all()]

@router.post("/")
async def create_template(req: TemplateCreateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(func.coalesce(func.max(PromptTemplate.version), 0)).where(PromptTemplate.template_name == req.template_name))
    next_ver = result.scalar() + 1
    for old in (await db.execute(select(PromptTemplate).where(PromptTemplate.template_name == req.template_name, PromptTemplate.is_active == True))).scalars().all():
        old.is_active = False
    t = PromptTemplate(
        template_name=req.template_name, version=next_ver, is_active=True,
        content=req.content, variables_used=req.variables_used,
        tone_parameters=req.tone_parameters, notes=req.notes,
        author=user.email,
    )
    db.add(t)
    await db.flush()
    db.add(
        AuditLog(
            user_id=user.id,
            action="template.create",
            target_type="template",
            target_id=str(t.id),
            detail={
                "template_name": t.template_name,
                "version": t.version,
                "is_active": t.is_active,
            },
        )
    )
    return {"id": str(t.id), "version": next_ver}

@router.post("/{template_id}/rollback")
async def rollback_template(template_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    target = await db.get(PromptTemplate, template_id)
    if not target:
        raise HTTPException(status_code=404, detail="Template not found")
    # Deactivate current active version of same template_name
    current = (await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.template_name == target.template_name,
            PromptTemplate.is_active == True,
        )
    )).scalars().all()
    for c in current:
        c.is_active = False
    target.is_active = True
    db.add(
        AuditLog(
            user_id=user.id,
            action="template.rollback",
            target_type="template",
            target_id=str(template_id),
            detail={"template_name": target.template_name, "activated_version": target.version},
        )
    )
    return {"status": "ok", "activated_version": target.version}
