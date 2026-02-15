"""API source adapters."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from voidwire.models import NewsSource

logger = logging.getLogger(__name__)


async def fetch_api_source(source: NewsSource) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(source.url)
            response.raise_for_status()
            data = response.json()
        items = data.get("items", []) if isinstance(data, dict) else data
        return [
            {
                "source_id": str(source.id),
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "full_text": None,
                "url": item.get("url", ""),
                "published_at": None,
                "domain": source.domain,
                "weight": source.weight,
            }
            for item in items[: source.max_articles]
            if isinstance(item, dict)
        ]
    except Exception as e:
        logger.warning("API fetch failed: %s", e)
        return []
