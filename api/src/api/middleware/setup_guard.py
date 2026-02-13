"""Setup guard middleware."""
from __future__ import annotations
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)
ALLOWED_PATHS = {"/setup", "/health", "/docs", "/openapi.json"}

class SetupGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in ALLOWED_PATHS):
            return await call_next(request)
        if not hasattr(request.app.state, "_setup_complete"):
            request.app.state._setup_complete = await _check_setup()
        if not request.app.state._setup_complete:
            return Response(content='{"detail":"Setup not complete","redirect":"/setup"}', status_code=503, media_type="application/json")
        return await call_next(request)

async def _check_setup() -> bool:
    try:
        from voidwire.database import get_session
        from voidwire.models import SetupState
        async with get_session() as session:
            state = await session.get(SetupState, 1)
            return state is not None and state.is_complete
    except Exception:
        return False
