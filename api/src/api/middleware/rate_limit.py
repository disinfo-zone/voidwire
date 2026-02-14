"""Rate limiting middleware."""
from __future__ import annotations

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from voidwire.config import get_settings

logger = logging.getLogger(__name__)


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
        settings = get_settings()
        client_ip = request.client.host if request.client else "unknown"
        try:
            r = await self._get_redis_client(request)
            key = f"ratelimit:{client_ip}:{int(time.time()//3600)}"
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
