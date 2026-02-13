"""RSS feed fetcher."""
from __future__ import annotations
import logging
from typing import Any
import httpx

logger = logging.getLogger(__name__)

async def fetch_rss(source_id: str, url: str, max_articles: int = 10, domain: str = "anomalous", weight: float = 0.5, allow_fulltext: bool = False) -> list[dict[str, Any]]:
    import feedparser
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()
    feed = feedparser.parse(response.text)
    articles = []
    for entry in feed.entries[:max_articles]:
        articles.append({"source_id": source_id, "title": getattr(entry,"title",""), "summary": getattr(entry,"summary",""), "full_text": None, "url": getattr(entry,"link",""), "published_at": getattr(entry,"published",None), "domain": domain, "weight": weight})
    return articles
