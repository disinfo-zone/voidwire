"""Admin audit log."""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AuditLog, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

@router.get("/")
async def list_audit(
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.where(AuditLog.action == action)
    if target_type:
        query = query.where(AuditLog.target_type == target_type)
    if target_id:
        query = query.where(AuditLog.target_id == target_id)
    if date_from:
        query = query.where(AuditLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(AuditLog.created_at <= datetime.fromisoformat(date_to))
    result = await db.execute(query.offset((page-1)*50).limit(50))
    return [
        {
            "id": str(e.id), "user_id": str(e.user_id) if e.user_id else None,
            "action": e.action, "target_type": e.target_type,
            "target_id": e.target_id, "detail": e.detail,
            "ip_address": str(e.ip_address) if e.ip_address else None,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in result.scalars().all()
    ]
