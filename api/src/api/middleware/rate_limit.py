"""Rate limiting middleware."""

from __future__ import annotations

import logging
import time
from ipaddress import ip_address, ip_network

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from voidwire.config import get_settings

logger = logging.getLogger(__name__)

_TRUSTED_PROXY_NETWORKS = (
    ip_network("127.0.0.0/8"),
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("::1/128"),
    ip_network("fc00::/7"),
)

_EXEMPT_PATHS = {
    "/v1/site/config",
    "/v1/stripe/webhook",
}

_AUTH_RATE_LIMITS: dict[str, int] = {
    "/v1/user/auth/register": 5,
    "/v1/user/auth/login": 20,
    "/v1/user/auth/oauth/google": 20,
    "/v1/user/auth/oauth/apple": 20,
    "/v1/user/auth/forgot-password": 3,
    "/v1/user/auth/reset-password": 8,
    "/v1/user/auth/verify-email": 8,
    "/v1/user/auth/resend-verification": 5,
}


def _is_valid_ip(value: str) -> bool:
    try:
        ip_address(value)
    except ValueError:
        return False
    return True


def _is_trusted_proxy_host(host: str) -> bool:
    if not host:
        return False
    if host == "testclient":
        return True
    try:
        addr = ip_address(host)
    except ValueError:
        return False
    return any(addr in net for net in _TRUSTED_PROXY_NETWORKS)


def _extract_forwarded_client_ip(x_forwarded_for: str) -> str | None:
    # Walk from right-to-left to ignore spoofed left-most entries and prefer the
    # nearest non-proxy public/client IP when a trusted proxy appends addresses.
    candidates = [part.strip() for part in x_forwarded_for.split(",") if part.strip()]
    for candidate in reversed(candidates):
        if not _is_valid_ip(candidate):
            continue
        if not _is_trusted_proxy_host(candidate):
            return candidate
    for candidate in reversed(candidates):
        if _is_valid_ip(candidate):
            return candidate
    return None


def _resolve_client_ip(request: Request) -> str:
    remote_host = request.client.host if request.client else "unknown"
    if _is_trusted_proxy_host(remote_host):
        forwarded = request.headers.get("x-forwarded-for", "")
        forwarded_ip = _extract_forwarded_client_ip(forwarded)
        if forwarded_ip:
            return forwarded_ip
    return remote_host


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def _get_redis_client(self, request: Request):
        redis_client = getattr(request.app.state, "_rate_limit_redis", None)
        if redis_client is None:
            import redis.asyncio as aioredis

            settings = get_settings()
            redis_client = aioredis.from_url(settings.redis_url)
            request.app.state._rate_limit_redis = redis_client
        return redis_client

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        settings = get_settings()
        client_ip = _resolve_client_ip(request)

        # Stricter per-endpoint auth rate limits
        auth_limit = _AUTH_RATE_LIMITS.get(request.url.path)
        if auth_limit and request.method == "POST":
            try:
                r = await self._get_redis_client(request)
                auth_key = (
                    f"ratelimit:auth:{request.url.path}:{client_ip}:{int(time.time() // 3600)}"
                )
                auth_count = await r.incr(auth_key)
                if auth_count == 1:
                    await r.expire(auth_key, 3600)
                if auth_count > auth_limit:
                    return Response(
                        content='{"detail":"Rate limit exceeded"}',
                        status_code=429,
                        media_type="application/json",
                    )
            except Exception as e:
                logger.warning("Auth rate limit check failed: %s", e)

        if settings.rate_limit_per_hour <= 0:
            return await call_next(request)
        try:
            r = await self._get_redis_client(request)
            key = f"ratelimit:{client_ip}:{int(time.time() // 3600)}"
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 3600)
            if count > settings.rate_limit_per_hour:
                return Response(
                    content='{"detail":"Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json",
                )
        except Exception as e:
            logger.warning("Rate limit check failed: %s", e)
        return await call_next(request)
