"""Content filters."""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)

def apply_domain_caps(articles: list[dict[str, Any]], max_per_domain: int = 15, max_total: int = 80) -> list[dict[str, Any]]:
    sorted_articles = sorted(articles, key=lambda a: a.get("weight", 0.5), reverse=True)
    domain_counts: dict[str, int] = {}
    capped = []
    for article in sorted_articles:
        if len(capped) >= max_total:
            break
        domain = article.get("domain", "unknown")
        if domain_counts.get(domain, 0) >= max_per_domain:
            continue
        capped.append(article)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    return capped

def filter_noise(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    noise = {"scores","standings","box score","celebrity","gossip","horoscope","zodiac sign"}
    return [a for a in articles if not any(kw in (a.get("title","")+" "+a.get("summary","")).lower() for kw in noise)]
