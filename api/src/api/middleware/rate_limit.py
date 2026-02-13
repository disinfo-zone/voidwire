"""Rate limiting middleware."""
from __future__ import annotations
import logging, time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from voidwire.config import get_settings

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)
        settings = get_settings()
        client_ip = request.client.host if request.client else "unknown"
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url)
            key = f"ratelimit:{client_ip}:{int(time.time()//3600)}"
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 3600)
            await r.aclose()
            if count > settings.rate_limit_per_hour:
                return Response(content='{"detail":"Rate limit exceeded"}', status_code=429, media_type="application/json")
        except Exception as e:
            logger.warning("Rate limit check failed: %s", e)
        return await call_next(request)
