"""Admin prompt template management."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import PromptTemplate, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

class TemplateCreateRequest(BaseModel):
    template_name: str
    content: str
    variables_used: list[str] = []

@router.get("/")
async def list_templates(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.is_active == True))
    return [{"id": str(t.id), "template_name": t.template_name, "version": t.version, "content": t.content} for t in result.scalars().all()]

@router.post("/")
async def create_template(req: TemplateCreateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(func.coalesce(func.max(PromptTemplate.version), 0)).where(PromptTemplate.template_name == req.template_name))
    next_ver = result.scalar() + 1
    for old in (await db.execute(select(PromptTemplate).where(PromptTemplate.template_name == req.template_name, PromptTemplate.is_active == True))).scalars().all():
        old.is_active = False
    t = PromptTemplate(template_name=req.template_name, version=next_ver, is_active=True, content=req.content, variables_used=req.variables_used, author=user.email)
    db.add(t)
    await db.flush()
    return {"id": str(t.id), "version": next_ver}
