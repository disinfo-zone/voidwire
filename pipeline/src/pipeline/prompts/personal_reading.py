"""Prompt builders for personalized readings."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

PERSONAL_READING_FREE_TEMPLATE_CANDIDATES = (
    "personal_reading_free",
    "personal_reading_free_v1",
    "starter_personal_reading_free",
)
PERSONAL_READING_PRO_TEMPLATE_CANDIDATES = (
    "personal_reading_pro",
    "personal_reading_pro_v1",
    "starter_personal_reading_pro",
)
PERSONAL_READING_FREE_TEMPLATE_PREFIX = "personal_reading_free"
PERSONAL_READING_PRO_TEMPLATE_PREFIX = "personal_reading_pro"
TEMPLATE_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _normalized_template_name(value: str | None, fallback: str) -> str:
    candidate = str(value or "").strip().lower()
    return candidate or fallback


def resolve_personal_template_candidates(tier: str, configured_template_name: str | None) -> tuple[str, ...]:
    """Return ordered unique template candidates, preferring configured name first."""
    if tier == "free":
        fallback = PERSONAL_READING_FREE_TEMPLATE_PREFIX
        defaults = PERSONAL_READING_FREE_TEMPLATE_CANDIDATES
    else:
        fallback = PERSONAL_READING_PRO_TEMPLATE_PREFIX
        defaults = PERSONAL_READING_PRO_TEMPLATE_CANDIDATES

    configured = _normalized_template_name(configured_template_name, fallback)
    ordered = [configured, *defaults]
    deduped: list[str] = []
    seen: set[str] = set()
    for name in ordered:
        key = str(name).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    return tuple(deduped)


def _format_natal_positions(positions: list[dict]) -> str:
    lines = []
    for p in positions:
        retro = " (R)" if p.get("retrograde") else ""
        house = f" in House {p['house']}" if p.get("house") else ""
        lines.append(f"  {p['body'].title()}: {p['degree']:.1f}° {p['sign']}{retro}{house}")
    return "\n".join(lines)


def _format_natal_angles(angles: list[dict]) -> str:
    return "\n".join(f"  {a['name']}: {a['degree']:.1f}° {a['sign']}" for a in angles)


def _format_transit_aspects(aspects: list[dict]) -> str:
    if not aspects:
        return "  (no close transit-to-natal aspects for this period)"
    lines = []
    for a in aspects:
        day_prefix = f"[{a['date']}] " if a.get("date") else ""
        lines.append(
            f"  {day_prefix}Transit {a['transit_body'].title()} {a['type']} Natal {a['natal_body'].title()} "
            f"(orb: {a['orb_degrees']:.2f}°, {a['significance']})"
        )
    return "\n".join(lines[:15])


def _format_current_transits(positions: dict) -> str:
    lines = []
    for body, data in positions.items():
        retro = " (R)" if data.get("retrograde") else ""
        lines.append(
            f"  {body.title()}: {data.get('degree', 0):.1f}° {data.get('sign', '?')}{retro}"
        )
    return "\n".join(lines)


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


def _render_template(template_text: str, context: dict[str, Any]) -> str:
    lookup = dict(context)
    lookup.update({str(k).lower(): v for k, v in context.items()})

    def replace(match: re.Match[str]) -> str:
        token = match.group(1).strip()
        if token in lookup:
            return _serialize_template_value(lookup[token])
        lowered = token.lower()
        if lowered in lookup:
            return _serialize_template_value(lookup[lowered])
        return ""

    return TEMPLATE_TOKEN_RE.sub(replace, template_text)


def _build_system_message(tier: str, blocked_words: list[str], word_range: list[int]) -> str:
    blocked_clause = (
        f" Never use these words or phrases: {', '.join(blocked_words[:40])}."
        if blocked_words
        else ""
    )
    min_words = int(word_range[0]) if len(word_range) > 0 else (300 if tier == "free" else 600)
    max_words = int(word_range[1]) if len(word_range) > 1 else (500 if tier == "free" else 1000)
    if tier == "free":
        return (
            "You are a skilled astrologer writing a personalized weekly horoscope. "
            "Write in second person ('you'). Be specific about the astrological influences at play. "
            "Do NOT use cliches like 'buckle up', 'wild ride', 'the universe has plans', or 'cosmic energy'. "
            "Write in a contemplative, slightly literary tone."
            f" Keep the output between {min_words} and {max_words} words."
            f"{blocked_clause} "
            "Return ONLY valid JSON with this schema: "
            '{"title": "string", "body": "string (plain text, use \\n\\n for paragraphs)", '
            '"sections": [], "word_count": number, "transit_highlights": ["string"]}'
        )
    return (
        "You are a skilled astrologer writing a detailed personalized daily horoscope. "
        "Write in second person ('you'). Be specific about astrological influences. "
        "Include sections for different life areas. "
        "Do NOT use cliches like 'buckle up', 'wild ride', 'the universe has plans', or 'cosmic energy'. "
        "Write in a contemplative, slightly literary tone."
        f" Keep the output between {min_words} and {max_words} words."
        f"{blocked_clause} "
        "Return ONLY valid JSON with this schema: "
        '{"title": "string", "body": "string (plain text, use \\n\\n for paragraphs)", '
        '"sections": [{"heading": "string", "body": "string"}], '
        '"word_count": number, "transit_highlights": ["string"]}'
    )


def build_free_reading_prompt(
    natal_positions: list[dict],
    natal_angles: list[dict],
    current_transits: dict,
    transit_to_natal: list[dict],
    house_system: str,
    date_context: date,
    week_start: date,
    week_end: date,
    blocked_words: list[str] | None = None,
    word_range: list[int] | None = None,
    template_text: str | None = None,
) -> list[dict]:
    """Build prompt for a free-tier weekly personal reading (300-500 words)."""
    asc = next((a for a in natal_angles if a["name"] == "Ascendant"), None)
    asc_str = f"{asc['sign']} Rising" if asc else "unknown Rising"
    blocked = [w.strip() for w in (blocked_words or []) if str(w).strip()]
    effective_range = word_range if isinstance(word_range, list) and len(word_range) == 2 else [300, 500]
    min_words = int(effective_range[0])
    max_words = int(effective_range[1])

    context = {
        "date_context": date_context,
        "week_start": week_start,
        "week_end": week_end,
        "house_system": house_system,
        "ascendant_label": asc_str,
        "natal_positions": _format_natal_positions(natal_positions),
        "natal_angles": _format_natal_angles(natal_angles),
        "current_transits": _format_current_transits(current_transits),
        "transit_to_natal": _format_transit_aspects(transit_to_natal),
        "word_range": [min_words, max_words],
        "banned_phrases": blocked,
    }

    if template_text:
        user = _render_template(template_text, context)
    else:
        user = f"""Generate a personalized weekly horoscope covering
{week_start.isoformat()} through {week_end.isoformat()}.
Use {date_context.isoformat()} as today's anchor date within that week.

NATAL CHART ({house_system} houses, {asc_str}):
{context['natal_positions']}

Angles:
{context['natal_angles']}

CURRENT TRANSITS:
{context['current_transits']}

TRANSIT-TO-NATAL ASPECTS (across this week):
{context['transit_to_natal']}

Write a {min_words}-{max_words} word weekly reading. Focus on the most significant transit-to-natal aspects.
Return ONLY the JSON object."""

    return [
        {"role": "system", "content": _build_system_message("free", blocked, [min_words, max_words])},
        {"role": "user", "content": user},
    ]


def build_pro_reading_prompt(
    natal_positions: list[dict],
    natal_angles: list[dict],
    current_transits: dict,
    transit_to_natal: list[dict],
    house_system: str,
    date_context: date,
    daily_reading_context: dict | None = None,
    blocked_words: list[str] | None = None,
    word_range: list[int] | None = None,
    template_text: str | None = None,
) -> list[dict]:
    """Build prompt for a pro-tier daily personal reading (600-1000 words)."""
    asc = next((a for a in natal_angles if a["name"] == "Ascendant"), None)
    asc_str = f"{asc['sign']} Rising" if asc else "unknown Rising"
    blocked = [w.strip() for w in (blocked_words or []) if str(w).strip()]
    effective_range = word_range if isinstance(word_range, list) and len(word_range) == 2 else [600, 1000]
    min_words = int(effective_range[0])
    max_words = int(effective_range[1])

    daily_ctx = ""
    if daily_reading_context:
        title = daily_reading_context.get("title", "")
        body_preview = daily_reading_context.get("body", "")[:500]
        daily_ctx = (
            "DAILY COLLECTIVE READING CONTEXT:\n"
            f"  Title: {title}\n"
            f"  Themes: {body_preview}...\n"
        )

    context = {
        "date_context": date_context,
        "house_system": house_system,
        "ascendant_label": asc_str,
        "natal_positions": _format_natal_positions(natal_positions),
        "natal_angles": _format_natal_angles(natal_angles),
        "current_transits": _format_current_transits(current_transits),
        "transit_to_natal": _format_transit_aspects(transit_to_natal),
        "daily_reading_context": daily_ctx or "(none)",
        "word_range": [min_words, max_words],
        "banned_phrases": blocked,
    }

    if template_text:
        user = _render_template(template_text, context)
    else:
        user = f"""Generate a personalized daily horoscope for {date_context.isoformat()}.

NATAL CHART ({house_system} houses, {asc_str}):
{context['natal_positions']}

Angles:
{context['natal_angles']}

CURRENT TRANSITS:
{context['current_transits']}

TRANSIT-TO-NATAL ASPECTS (today):
{context['transit_to_natal']}
{daily_ctx}
Write a {min_words}-{max_words} word daily reading with sections for key life areas affected by today's transits.
Return ONLY the JSON object."""

    return [
        {"role": "system", "content": _build_system_message("pro", blocked, [min_words, max_words])},
        {"role": "user", "content": user},
    ]
