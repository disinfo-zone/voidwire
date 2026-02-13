"""Admin backup management."""
from fastapi import APIRouter, Depends
from voidwire.models import AdminUser
from api.dependencies import get_db, require_admin
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.get("/")
async def list_backups(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    return {"backups": []}

@router.post("/create")
async def create_backup(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    return {"status": "not_implemented"}
