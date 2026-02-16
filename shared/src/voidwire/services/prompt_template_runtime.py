"""Runtime prompt-template utilities shared by API and pipeline flows."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from voidwire.models import PromptTemplate

TEMPLATE_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _serialize_template_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    try:
        return json.dumps(value, indent=2, default=str)
    except Exception:
        return str(value)


def render_prompt_template(template_text: str, context: dict[str, Any]) -> str:
    """Render {{token}} placeholders from a plain dict context."""
    lookup = dict(context)
    lookup.update({str(k).lower(): v for k, v in context.items()})

    def _replace(match: re.Match[str]) -> str:
        token = match.group(1).strip()
        if token in lookup:
            return _serialize_template_value(lookup[token])
        lowered = token.lower()
        if lowered in lookup:
            return _serialize_template_value(lookup[lowered])
        return ""

    return TEMPLATE_TOKEN_RE.sub(_replace, template_text)


def template_usage(template: PromptTemplate) -> dict[str, Any]:
    return {
        "id": str(template.id),
        "template_name": str(template.template_name),
        "version": int(template.version),
    }


async def load_active_prompt_template(
    session: AsyncSession,
    *,
    candidates: tuple[str, ...] | list[str] | None = None,
    prefix: str | None = None,
) -> PromptTemplate | None:
    """Resolve one active template by exact name candidates, then prefix fallback."""
    normalized_candidates = [str(c).strip().lower() for c in (candidates or []) if str(c).strip()]
    if normalized_candidates:
        result = await session.execute(
            select(PromptTemplate).where(
                PromptTemplate.is_active.is_(True),
                func.lower(PromptTemplate.template_name).in_(normalized_candidates),
            )
        )
        exact_hits = result.scalars().all()
        if exact_hits:
            by_name_index = {name: index for index, name in enumerate(normalized_candidates)}
            exact_hits.sort(
                key=lambda tpl: (
                    by_name_index.get(str(tpl.template_name).strip().lower(), len(normalized_candidates)),
                    -int(tpl.version or 0),
                )
            )
            return exact_hits[0]

    prefix_lc = str(prefix or "").strip().lower()
    if not prefix_lc:
        return None

    result = await session.execute(
        select(PromptTemplate).where(
            PromptTemplate.is_active.is_(True),
            func.lower(PromptTemplate.template_name).like(f"{prefix_lc}%"),
        )
    )
    prefix_hits = result.scalars().all()
    if not prefix_hits:
        return None

    prefix_hits.sort(
        key=lambda tpl: (
            int(tpl.version or 0),
            str(tpl.template_name),
        ),
        reverse=True,
    )
    return prefix_hits[0]

