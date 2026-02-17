"""Prompt template defaults and bootstrap helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import PromptTemplate

STARTER_PROSE_TEMPLATE_NAME = "starter_synthesis_prose"
STARTER_PROSE_TEMPLATE_CONTENT = """You are a cultural seismograph reading the world through astrological symbolism.

TODAY: {{date_context}}

=== TRANSIT DATA ===
{{ephemeris_data}}

=== CULTURAL SIGNALS ===
{{selected_signals}}

=== ACTIVE THREADS ===
{{thread_snapshot}}

=== INTERPRETIVE PLAN ===
{{interpretive_plan}}

=== MENTION POLICY ===
{{mention_policy}}

=== GUARDED ENTITIES ===
{{guarded_entities}}

=== SKY-ONLY MODE ===
{{sky_only}}

HARD CONSTRAINTS:
- Return strict JSON only (no markdown fencing).
- No emojis.
- Keep tone precise, unsentimental, and allusion-first.
- Never address the reader directly as "you".
- Standard reading body target: {{standard_word_range}} words.
- Extended reading target: {{extended_word_range}} words.
- Avoid banned phrases: {{banned_phrases}}
- Respect explicit mention policy and guarded entity constraints above.

STANDARD vs EXTENDED:
- `standard_reading` is the front-page dispatch: one coherent title/body unit.
- `extended_reading` deepens the same thesis using multiple sections and sub-arguments.
- Both should reference the same core celestial pattern, but at different levels of depth.

Write JSON with:
- standard_reading: {title, body, word_count}
- extended_reading: {title, subtitle, sections: [{heading, body}], word_count}
- transit_annotations: [{aspect, gloss, cultural_resonance, temporal_arc}]
"""

STARTER_PROSE_TEMPLATE_VARIABLES = [
    "date_context",
    "ephemeris_data",
    "selected_signals",
    "thread_snapshot",
    "interpretive_plan",
    "mention_policy",
    "guarded_entities",
    "sky_only",
    "standard_word_range",
    "extended_word_range",
    "banned_phrases",
]

STARTER_PLAN_TEMPLATE_NAME = "synthesis_plan"
STARTER_PLAN_TEMPLATE_CONTENT = """You are a cultural seismograph reading the world through astrological symbolism.

TODAY: {{date_context}}

=== TRANSIT DATA ===
{{ephemeris_data}}

=== CULTURAL SIGNALS ===
{{selected_signals}}

=== ACTIVE THREADS ===
{{thread_snapshot}}

SKY-ONLY MODE:
{{sky_only}}

Produce an INTERPRETIVE PLAN as JSON with these fields:
- title: Working title for the reading
- opening_strategy: How to open (which transit or signal leads)
- closing_strategy: How to close (resolution, lingering tension, etc.)
- wild_card_integration: How to weave the wild card signal (if any) into the narrative
- aspect_readings: Array of {aspect, interpretation, cultural_link} for each major transit
- tone_notes: Prose style guidance (register, metaphor family, rhythm)
- thread_continuity: Which active threads to reference and how
- mention_policy: {
    explicit_allowed: boolean (default false),
    explicit_budget: integer (0 or 1),
    allowed_entities: string[] (entities that may be named directly if explicit_allowed=true),
    rationale: string
  }

Critical instruction:
- Allusion first. Prefer symbolic framing and subtext over direct event references.
- Explicit named references are allowed only when a connection is undeniable and structurally central.

Return ONLY valid JSON, no markdown fencing.
"""

STARTER_PLAN_TEMPLATE_VARIABLES = [
    "date_context",
    "ephemeris_data",
    "selected_signals",
    "thread_snapshot",
    "sky_only",
]

STARTER_EVENT_PROSE_TEMPLATE_NAME = "starter_synthesis_event_prose"
STARTER_EVENT_PROSE_TEMPLATE_CONTENT = """You are writing an event-focused astrological dispatch.

TODAY: {{date_context}}

=== EVENT CONTEXT (PRIMARY FOCUS) ===
{{event_context}}

=== TRANSIT DATA ===
{{ephemeris_data}}

=== CULTURAL SIGNALS (SECONDARY TEXTURE) ===
{{selected_signals}}

=== ACTIVE THREADS (SECONDARY TEXTURE) ===
{{thread_snapshot}}

=== INTERPRETIVE PLAN ===
{{interpretive_plan}}

=== MENTION POLICY ===
{{mention_policy}}

=== GUARDED ENTITIES ===
{{guarded_entities}}

=== SKY-ONLY MODE ===
{{sky_only}}

HARD CONSTRAINTS:
- Return strict JSON only (no markdown fencing).
- No emojis.
- Never address the reader directly as "you".
- The event in EVENT CONTEXT must be the central frame from opening to close.
- Signals and threads may color the reading but cannot displace the event as primary.
- Standard reading body target: {{standard_word_range}} words.
- Extended reading target: {{extended_word_range}} words.
- Avoid banned phrases: {{banned_phrases}}
- Respect explicit mention policy and guarded entity constraints above.

STRUCTURE:
- standard_reading: concise front-page event dispatch with one coherent thesis.
- extended_reading: deeper event analysis with multiple sections.
- transit_annotations: tie specific aspects to the event arc.

Write JSON with:
- standard_reading: {title, body, word_count}
- extended_reading: {title, subtitle, sections: [{heading, body}], word_count}
- transit_annotations: [{aspect, gloss, cultural_resonance, temporal_arc}]
"""

STARTER_EVENT_PROSE_TEMPLATE_VARIABLES = [
    "date_context",
    "event_context",
    "ephemeris_data",
    "selected_signals",
    "thread_snapshot",
    "interpretive_plan",
    "mention_policy",
    "guarded_entities",
    "sky_only",
    "standard_word_range",
    "extended_word_range",
    "banned_phrases",
]

STARTER_EVENT_PLAN_TEMPLATE_NAME = "starter_synthesis_event_plan"
STARTER_EVENT_PLAN_TEMPLATE_CONTENT = """You are drafting an event-focused interpretive plan.

TODAY: {{date_context}}

=== EVENT CONTEXT (PRIMARY FOCUS) ===
{{event_context}}

=== TRANSIT DATA ===
{{ephemeris_data}}

=== CULTURAL SIGNALS ===
{{selected_signals}}

=== ACTIVE THREADS ===
{{thread_snapshot}}

SKY-ONLY MODE:
{{sky_only}}

Produce an INTERPRETIVE PLAN as JSON with these fields:
- title
- opening_strategy
- closing_strategy
- wild_card_integration
- aspect_readings: [{aspect, interpretation, cultural_link}]
- tone_notes
- thread_continuity
- mention_policy: {
    explicit_allowed: boolean,
    explicit_budget: integer (0 or 1),
    allowed_entities: string[],
    rationale: string
  }

Critical instructions:
- Anchor every planning decision to the event context first.
- Treat signals and threads as supporting texture, not primary thesis.

Return ONLY valid JSON, no markdown fencing.
"""

STARTER_EVENT_PLAN_TEMPLATE_VARIABLES = [
    "date_context",
    "event_context",
    "ephemeris_data",
    "selected_signals",
    "thread_snapshot",
    "sky_only",
]

STARTER_PERSONAL_FREE_TEMPLATE_NAME = "starter_personal_reading_free"
STARTER_PERSONAL_FREE_TEMPLATE_CONTENT = """You are a skilled astrologer writing a weekly natal-transit reading.

TODAY: {{date_context}}
WEEK COVERAGE: {{week_start}} to {{week_end}}
HOUSE SYSTEM: {{house_system}}
ASCENDANT: {{ascendant_label}}

=== NATAL POSITIONS ===
{{natal_positions}}

=== NATAL ANGLES ===
{{natal_angles}}

=== CURRENT TRANSITS (TODAY) ===
{{current_transits}}

=== TRANSIT-TO-NATAL ASPECTS (WEEK) ===
{{transit_to_natal}}

=== BANNED PHRASES ===
{{banned_phrases}}

HARD CONSTRAINTS:
- Return strict JSON only (no markdown fencing).
- Write in second person ("you").
- Do not use cliches like "buckle up", "wild ride", "universe has plans", or "cosmic energy".
- Do not use banned phrases listed above.
- Keep body within {{word_range}} words.

Return JSON with:
- title: string
- body: string (plain text, use \\n\\n for paragraph breaks)
- sections: [] (free tier should usually be empty)
- word_count: number
- transit_highlights: string[]
"""

STARTER_PERSONAL_FREE_TEMPLATE_VARIABLES = [
    "date_context",
    "week_start",
    "week_end",
    "house_system",
    "ascendant_label",
    "natal_positions",
    "natal_angles",
    "current_transits",
    "transit_to_natal",
    "word_range",
    "banned_phrases",
]

STARTER_PERSONAL_PRO_TEMPLATE_NAME = "starter_personal_reading_pro"
STARTER_PERSONAL_PRO_TEMPLATE_CONTENT = """You are a skilled astrologer writing a detailed daily natal-transit reading.

TODAY: {{date_context}}
HOUSE SYSTEM: {{house_system}}
ASCENDANT: {{ascendant_label}}

=== NATAL POSITIONS ===
{{natal_positions}}

=== NATAL ANGLES ===
{{natal_angles}}

=== CURRENT TRANSITS ===
{{current_transits}}

=== TRANSIT-TO-NATAL ASPECTS (TODAY) ===
{{transit_to_natal}}

=== DAILY COLLECTIVE CONTEXT ===
{{daily_reading_context}}

=== BANNED PHRASES ===
{{banned_phrases}}

HARD CONSTRAINTS:
- Return strict JSON only (no markdown fencing).
- Write in second person ("you").
- Do not use cliches like "buckle up", "wild ride", "universe has plans", or "cosmic energy".
- Do not use banned phrases listed above.
- Body target: {{word_range}} words.
- Include sections for key life areas.

Return JSON with:
- title: string
- body: string (plain text, use \\n\\n for paragraph breaks)
- sections: [{heading, body}]
- word_count: number
- transit_highlights: string[]
"""

STARTER_PERSONAL_PRO_TEMPLATE_VARIABLES = [
    "date_context",
    "house_system",
    "ascendant_label",
    "natal_positions",
    "natal_angles",
    "current_transits",
    "transit_to_natal",
    "daily_reading_context",
    "word_range",
    "banned_phrases",
]


STARTER_CELESTIAL_WEATHER_TEMPLATE_NAME = "starter_celestial_weather"
STARTER_CELESTIAL_WEATHER_TEMPLATE_CONTENT = """You are a skilled astrologer writing brief celestial weather descriptions for today.

TODAY: {{date_context}}

=== EPHEMERIS DATA ===
{{ephemeris_data}}

Write concise, evocative descriptions for today's celestial weather. Match the site's tone: precise, literary, unsentimental. No clichés. No emojis. Each description should be 1-2 sentences.

HARD CONSTRAINTS:
- Return strict JSON only (no markdown fencing).
- Write in English only. No non-Latin characters.

Return JSON with:
- moon_phase: string (current moon phase and its emotional/energetic meaning)
- void_of_course: string (VOC status and what it means for the day)
- retrogrades: string or null (summary of active retrogrades, null if none)
- timeline: array of strings, one 1-sentence description per timeline event listed above, in the same order
"""

STARTER_CELESTIAL_WEATHER_TEMPLATE_VARIABLES = [
    "date_context",
    "ephemeris_data",
]


def _build_starter_celestial_weather_template() -> PromptTemplate:
    return PromptTemplate(
        template_name=STARTER_CELESTIAL_WEATHER_TEMPLATE_NAME,
        version=1,
        is_active=True,
        content=STARTER_CELESTIAL_WEATHER_TEMPLATE_CONTENT,
        variables_used=STARTER_CELESTIAL_WEATHER_TEMPLATE_VARIABLES,
        tone_parameters={
            "register": "precise, literary, evocative",
            "style_notes": "brief weather-report style; symbolic but concrete",
        },
        author="system",
        notes="Auto-generated starter template for celestial weather descriptions.",
    )


def _build_starter_prose_template() -> PromptTemplate:
    return PromptTemplate(
        template_name=STARTER_PROSE_TEMPLATE_NAME,
        version=1,
        is_active=True,
        content=STARTER_PROSE_TEMPLATE_CONTENT,
        variables_used=STARTER_PROSE_TEMPLATE_VARIABLES,
        tone_parameters={
            "register": "analytical, literary, restrained",
            "style_notes": "image-rich but concrete",
        },
        author="system",
        notes="Auto-generated starter prose template for first-time setup.",
    )


def _build_starter_plan_template() -> PromptTemplate:
    return PromptTemplate(
        template_name=STARTER_PLAN_TEMPLATE_NAME,
        version=1,
        is_active=True,
        content=STARTER_PLAN_TEMPLATE_CONTENT,
        variables_used=STARTER_PLAN_TEMPLATE_VARIABLES,
        tone_parameters={
            "register": "strategic, symbolic, restrained",
            "style_notes": "allusion-first; avoid reportorial framing",
        },
        author="system",
        notes="Auto-generated starter plan template for first-time setup.",
    )


def _build_starter_event_prose_template() -> PromptTemplate:
    return PromptTemplate(
        template_name=STARTER_EVENT_PROSE_TEMPLATE_NAME,
        version=1,
        is_active=True,
        content=STARTER_EVENT_PROSE_TEMPLATE_CONTENT,
        variables_used=STARTER_EVENT_PROSE_TEMPLATE_VARIABLES,
        tone_parameters={
            "register": "focused, analytical, restrained",
            "style_notes": "event-first framing; keep signals secondary",
        },
        author="system",
        notes="Auto-generated starter prose template for event-linked readings.",
    )


def _build_starter_event_plan_template() -> PromptTemplate:
    return PromptTemplate(
        template_name=STARTER_EVENT_PLAN_TEMPLATE_NAME,
        version=1,
        is_active=True,
        content=STARTER_EVENT_PLAN_TEMPLATE_CONTENT,
        variables_used=STARTER_EVENT_PLAN_TEMPLATE_VARIABLES,
        tone_parameters={
            "register": "strategic, event-centric, restrained",
            "style_notes": "event-focused planning with symbolic rigor",
        },
        author="system",
        notes="Auto-generated starter plan template for event-linked readings.",
    )


def _build_starter_personal_free_template() -> PromptTemplate:
    return PromptTemplate(
        template_name=STARTER_PERSONAL_FREE_TEMPLATE_NAME,
        version=1,
        is_active=True,
        content=STARTER_PERSONAL_FREE_TEMPLATE_CONTENT,
        variables_used=STARTER_PERSONAL_FREE_TEMPLATE_VARIABLES,
        tone_parameters={
            "register": "intimate, grounded, direct",
            "style_notes": "weekly cadence; transit-driven specificity",
        },
        author="system",
        notes="Auto-generated starter template for free weekly personal readings.",
    )


def _build_starter_personal_pro_template() -> PromptTemplate:
    return PromptTemplate(
        template_name=STARTER_PERSONAL_PRO_TEMPLATE_NAME,
        version=1,
        is_active=True,
        content=STARTER_PERSONAL_PRO_TEMPLATE_CONTENT,
        variables_used=STARTER_PERSONAL_PRO_TEMPLATE_VARIABLES,
        tone_parameters={
            "register": "detailed, reflective, practical",
            "style_notes": "daily cadence; sectioned life-domain guidance",
        },
        author="system",
        notes="Auto-generated starter template for pro daily personal readings.",
    )


async def ensure_starter_prompt_template(db: AsyncSession) -> list[PromptTemplate]:
    """Ensure baseline synthesis templates exist, backfilling missing starters."""
    result = await db.execute(select(PromptTemplate.template_name))
    existing_names = {str(name) for name in result.scalars().all() if str(name).strip()}

    starters = [
        _build_starter_prose_template(),
        _build_starter_plan_template(),
        _build_starter_event_prose_template(),
        _build_starter_event_plan_template(),
        _build_starter_personal_free_template(),
        _build_starter_personal_pro_template(),
        _build_starter_celestial_weather_template(),
    ]
    created: list[PromptTemplate] = []
    for starter in starters:
        if starter.template_name in existing_names:
            continue
        db.add(starter)
        created.append(starter)

    if created:
        await db.flush()
    return created
