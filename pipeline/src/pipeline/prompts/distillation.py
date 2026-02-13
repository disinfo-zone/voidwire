"""Distillation prompt builder."""
from __future__ import annotations
from typing import Any

def build_distillation_prompt(articles: list[dict[str, Any]]) -> str:
    article_text = ""
    for i, a in enumerate(articles, 1):
        content = a.get("full_text") or a.get("summary", "")
        if len(content) > 500:
            content = content[:500] + "..."
        article_text += f"\n[{i}] {a.get('title','Untitled')}\n{content}\n"
    return f"""You are a cultural analyst extracting archetypal currents from today's news.
For each significant development, extract:
1. A thematic summary (1-2 sentences, archetypal quality)
2. Domain: conflict|diplomacy|economy|technology|culture|environment|social|anomalous|legal|health
3. Intensity: major|moderate|minor
4. Directionality: escalating|stable|de-escalating|erupting|resolving
5. Key entities (archetypal framing)

From these {len(articles)} articles, extract 15-20 cultural signals.
Return as JSON array with fields: summary, domain, intensity, directionality, entities, source_refs.
No preamble, no markdown fencing.

ARTICLES:{article_text}

Return ONLY a JSON array."""
