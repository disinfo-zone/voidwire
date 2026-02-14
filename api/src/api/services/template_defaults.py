"""Prompt template defaults and bootstrap helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import PromptTemplate

STARTER_TEMPLATE_NAME = "starter_synthesis_prose"
STARTER_TEMPLATE_CONTENT = """You are a cultural seismograph reading the world through astrological symbolism.

TODAY: {{date_context}}

=== TRANSIT DATA ===
{{ephemeris_data}}

=== CULTURAL SIGNALS ===
{{selected_signals}}

=== ACTIVE THREADS ===
{{thread_snapshot}}

=== INTERPRETIVE PLAN ===
{{interpretive_plan}}

Write JSON with:
- standard_reading: {title, body, word_count}
- extended_reading: {title, subtitle, sections: [{heading, body}], word_count}
- transit_annotations: [{aspect, gloss, cultural_resonance, temporal_arc}]

Constraints:
- No markdown fencing
- No emojis
- Keep tone precise and unsentimental
- Never address the reader directly as "you"
"""

STARTER_TEMPLATE_VARIABLES = [
    "date_context",
    "ephemeris_data",
    "selected_signals",
    "thread_snapshot",
    "interpretive_plan",
]


def _build_starter_template() -> PromptTemplate:
    """Create one starter template for first-time users."""
    return PromptTemplate(
        template_name=STARTER_TEMPLATE_NAME,
        version=1,
        is_active=True,
        content=STARTER_TEMPLATE_CONTENT,
        variables_used=STARTER_TEMPLATE_VARIABLES,
        tone_parameters={
            "register": "analytical, literary, restrained",
            "style_notes": "image-rich but concrete",
        },
        author="system",
        notes="Auto-generated starter template to help first-time setup.",
    )


async def ensure_starter_prompt_template(db: AsyncSession) -> PromptTemplate | None:
    """Seed exactly one starter template only when the table is empty."""
    result = await db.execute(select(PromptTemplate.id).limit(1))
    if result.scalars().first() is not None:
        return None

    starter = _build_starter_template()
    db.add(starter)
    await db.flush()
    return starter
