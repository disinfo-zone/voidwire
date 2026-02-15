"""CSRF protection for cookie-authenticated unsafe requests."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from voidwire.config import get_settings

from api.dependencies import (
    ADMIN_AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    USER_AUTH_COOKIE_NAME,
)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXEMPT_PATH_PREFIXES = ("/v1/stripe/webhook",)


def _origin(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".lower()


def _allowed_origins() -> set[str]:
    settings = get_settings()
    allowed = {
        _origin(settings.site_url),
        _origin(settings.admin_url),
        _origin(settings.api_url),
    }
    return {entry for entry in allowed if entry}


def _request_origin(request: Request) -> str | None:
    header = request.headers.get("origin", "").strip()
    if header:
        return _origin(header)
    referer = request.headers.get("referer", "").strip()
    if referer:
        return _origin(referer)
    return None


def _has_auth_cookie(request: Request) -> bool:
    return bool(
        request.cookies.get(ADMIN_AUTH_COOKIE_NAME) or request.cookies.get(USER_AUTH_COOKIE_NAME)
    )


def _has_bearer_auth(request: Request) -> bool:
    auth = request.headers.get("authorization", "")
    return auth.lower().startswith("bearer ")


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        method = request.method.upper()
        if method not in UNSAFE_METHODS:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES):
            return await call_next(request)

        # CSRF is relevant for cookie-based auth sessions.
        if not _has_auth_cookie(request) or _has_bearer_auth(request):
            return await call_next(request)

        allowed = _allowed_origins()
        request_origin = _request_origin(request)
        if request_origin is not None and request_origin not in allowed:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Cross-site request origin is not allowed"},
            )

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "").strip()
        header_token = request.headers.get(CSRF_HEADER_NAME, "").strip()
        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Missing or invalid CSRF token"},
            )

        return await call_next(request)
