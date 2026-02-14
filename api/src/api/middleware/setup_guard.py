"""Setup guard middleware."""

from __future__ import annotations

import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from voidwire.config import get_settings

logger = logging.getLogger(__name__)
ALLOWED_PREFIXES = (
    "/setup",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class SetupGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if settings.skip_setup_guard:
            return await call_next(request)
        if any(request.url.path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            return await call_next(request)

        now = time.monotonic()
        setup_complete = getattr(request.app.state, "_setup_complete", None)
        checked_at = getattr(request.app.state, "_setup_checked_at", 0.0)

        should_refresh = setup_complete is None or (
            setup_complete is False and now - checked_at >= settings.setup_guard_recheck_seconds
        )
        if should_refresh:
            setup_complete = await _check_setup()
            request.app.state._setup_complete = setup_complete
            request.app.state._setup_checked_at = now

        if not request.app.state._setup_complete:
            return JSONResponse(
                status_code=503,
                content={"detail": "Setup not complete", "redirect": "/setup"},
            )
        return await call_next(request)


async def _check_setup() -> bool:
    try:
        from voidwire.database import get_session
        from voidwire.models import SetupState

        async with get_session() as session:
            state = await session.get(SetupState, 1)
            return state is not None and state.is_complete
    except Exception:
        logger.exception("Failed to resolve setup state")
        return False
