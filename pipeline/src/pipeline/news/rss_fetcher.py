"""RSS feed fetcher with optional full-text extraction."""
from __future__ import annotations
import logging
from typing import Any
import httpx

logger = logging.getLogger(__name__)
FULLTEXT_TIMEOUT = 5.0


async def fetch_rss(
    source_id: str,
    url: str,
    max_articles: int = 10,
    domain: str = "anomalous",
    weight: float = 0.5,
    allow_fulltext: bool = False,
) -> list[dict[str, Any]]:
    import feedparser

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()
    feed = feedparser.parse(response.text)
    articles = []
    for entry in feed.entries[:max_articles]:
        full_text = None
        link = getattr(entry, "link", "")

        if allow_fulltext and link:
            full_text = await _extract_fulltext(link)

        articles.append({
            "source_id": source_id,
            "title": getattr(entry, "title", ""),
            "summary": getattr(entry, "summary", ""),
            "full_text": full_text,
            "url": link,
            "published_at": getattr(entry, "published", None),
            "domain": domain,
            "weight": weight,
        })
    return articles


async def _extract_fulltext(url: str) -> str | None:
    """Extract full article text via trafilatura with timeout."""
    try:
        import trafilatura

        async with httpx.AsyncClient(timeout=FULLTEXT_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
        text = trafilatura.extract(response.text, include_comments=False, include_tables=False)
        if text and len(text) > 50:
            return text
    except ImportError:
        logger.debug("trafilatura not installed, skipping fulltext extraction")
    except Exception as e:
        logger.debug("Fulltext extraction failed for %s: %s", url, e)
    return None
