"""Health check."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "voidwire-api"}


@router.get("/health/ready")
async def readiness_check():
    try:
        from sqlalchemy import text
        from voidwire.database import get_session

        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(exc)},
        )
