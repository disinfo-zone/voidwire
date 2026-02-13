"""News ingestion stage."""
from __future__ import annotations
import logging
from datetime import date
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import NewsSource
from voidwire.services.pipeline_settings import IngestionSettings
from pipeline.news.rss_fetcher import fetch_rss
from pipeline.news.deduplication import deduplicate_articles
from pipeline.news.filters import apply_domain_caps

logger = logging.getLogger(__name__)

async def run_ingestion_stage(
    date_context: date,
    session: AsyncSession,
    settings: IngestionSettings | None = None,
) -> list[dict[str, Any]]:
    ing = settings or IngestionSettings()
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
                    fulltext_timeout=ing.fulltext_timeout, rss_timeout=ing.rss_timeout,
                )
                all_articles.extend(articles)
            source.last_fetch_at = date_context
            source.last_error = None
        except Exception as e:
            logger.warning("Source %s failed: %s", source.name, e)
            source.last_error = str(e)
            continue
    all_articles = deduplicate_articles(all_articles)
    all_articles = apply_domain_caps(all_articles, max_per_domain=ing.max_per_domain, max_total=ing.max_total)
    return all_articles
