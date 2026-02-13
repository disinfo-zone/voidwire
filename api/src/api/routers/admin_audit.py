"""Admin audit log."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AuditLog, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

@router.get("/")
async def list_audit(action: str | None = None, page: int = Query(default=1, ge=1), db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.where(AuditLog.action == action)
    result = await db.execute(query.offset((page-1)*50).limit(50))
    return [{"id": str(e.id), "action": e.action, "target_type": e.target_type, "created_at": e.created_at.isoformat() if e.created_at else None} for e in result.scalars().all()]
