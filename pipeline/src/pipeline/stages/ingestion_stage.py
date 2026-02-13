"""News ingestion stage."""
from __future__ import annotations
import logging
from datetime import date
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import NewsSource
from pipeline.news.rss_fetcher import fetch_rss
from pipeline.news.deduplication import deduplicate_articles
from pipeline.news.filters import apply_domain_caps

logger = logging.getLogger(__name__)

async def run_ingestion_stage(date_context: date, session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(select(NewsSource).where(NewsSource.status == "active"))
    sources = result.scalars().all()
    if not sources:
        return []
    all_articles: list[dict] = []
    for source in sources:
        try:
            if source.source_type == "rss":
                articles = await fetch_rss(
                    source_id=str(source.id), url=source.url,
                    max_articles=source.max_articles, domain=source.domain,
                    weight=source.weight, allow_fulltext=source.allow_fulltext_extract,
                )
                all_articles.extend(articles)
            source.last_fetch_at = date_context
            source.last_error = None
        except Exception as e:
            logger.warning("Source %s failed: %s", source.name, e)
            source.last_error = str(e)
            continue
    all_articles = deduplicate_articles(all_articles)
    all_articles = apply_domain_caps(all_articles, max_per_domain=15, max_total=80)
    return all_articles
