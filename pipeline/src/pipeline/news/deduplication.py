"""Article deduplication."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)


def deduplicate_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique = []
    for article in articles:
        url = _normalize_url(article.get("url", ""))
        if url in seen_urls:
            continue
        title = article.get("title", "").strip().lower()
        if title and title in seen_titles:
            continue
        seen_urls.add(url)
        if title:
            seen_titles.add(title)
        unique.append(article)
    return unique


def _normalize_url(url: str) -> str:
    try:
        p = urlparse(url)
        tracking = {"utm_source", "utm_medium", "utm_campaign", "ref", "fbclid", "gclid"}
        q = {k: v for k, v in parse_qs(p.query).items() if k.lower() not in tracking}
        return urlunparse(
            (
                p.scheme.lower(),
                p.netloc.lower(),
                p.path.rstrip("/"),
                p.params,
                urlencode(q, doseq=True),
                "",
            )
        )
    except Exception:
        return url
