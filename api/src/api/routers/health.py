"""Health check."""
from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "voidwire-api"}

@router.get("/health/ready")
async def readiness_check():
    try:
        from voidwire.database import get_session
        from sqlalchemy import text
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}
