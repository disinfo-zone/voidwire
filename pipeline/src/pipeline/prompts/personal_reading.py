"""Prompt builders for personalized readings."""

from __future__ import annotations

from datetime import date


def _format_natal_positions(positions: list[dict]) -> str:
    lines = []
    for p in positions:
        retro = " (R)" if p.get("retrograde") else ""
        house = f" in House {p['house']}" if p.get("house") else ""
        lines.append(f"  {p['body'].title()}: {p['degree']:.1f}° {p['sign']}{retro}{house}")
    return "\n".join(lines)


def _format_transit_aspects(aspects: list[dict]) -> str:
    if not aspects:
        return "  (no close transit-to-natal aspects today)"
    lines = []
    for a in aspects:
        lines.append(
            f"  Transit {a['transit_body'].title()} {a['type']} Natal {a['natal_body'].title()} "
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


def build_free_reading_prompt(
    natal_positions: list[dict],
    natal_angles: list[dict],
    current_transits: dict,
    transit_to_natal: list[dict],
    house_system: str,
    date_context: date,
) -> list[dict]:
    """Build prompt for a free-tier weekly personal reading (300-500 words)."""
    asc = next((a for a in natal_angles if a["name"] == "Ascendant"), None)
    asc_str = f"{asc['sign']} Rising" if asc else "unknown Rising"

    system = (
        "You are a skilled astrologer writing a personalized weekly horoscope. "
        "Write in second person ('you'). Be specific about the astrological influences at play. "
        "Do NOT use clichés like 'buckle up', 'wild ride', 'the universe has plans', or 'cosmic energy'. "
        "Write in a contemplative, slightly literary tone. "
        "Return ONLY valid JSON with this schema: "
        '{"title": "string", "body": "string (plain text, use \\n\\n for paragraphs)", '
        '"sections": [], "word_count": number, "transit_highlights": ["string"]}'
    )

    user = f"""Generate a personalized weekly horoscope for the week of {date_context.isoformat()}.

NATAL CHART ({house_system} houses, {asc_str}):
{_format_natal_positions(natal_positions)}

Angles:
{chr(10).join(f"  {a['name']}: {a['degree']:.1f}° {a['sign']}" for a in natal_angles)}

CURRENT TRANSITS:
{_format_current_transits(current_transits)}

TRANSIT-TO-NATAL ASPECTS (this week):
{_format_transit_aspects(transit_to_natal)}

Write a 300-500 word weekly reading. Focus on the most significant transit-to-natal aspects.
Return ONLY the JSON object."""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_pro_reading_prompt(
    natal_positions: list[dict],
    natal_angles: list[dict],
    current_transits: dict,
    transit_to_natal: list[dict],
    house_system: str,
    date_context: date,
    daily_reading_context: dict | None = None,
) -> list[dict]:
    """Build prompt for a pro-tier daily personal reading (600-1000 words)."""
    asc = next((a for a in natal_angles if a["name"] == "Ascendant"), None)
    asc_str = f"{asc['sign']} Rising" if asc else "unknown Rising"

    daily_ctx = ""
    if daily_reading_context:
        title = daily_reading_context.get("title", "")
        body_preview = daily_reading_context.get("body", "")[:500]
        daily_ctx = f"""
DAILY COLLECTIVE READING CONTEXT:
  Title: {title}
  Themes: {body_preview}...
"""

    system = (
        "You are a skilled astrologer writing a detailed personalized daily horoscope. "
        "Write in second person ('you'). Be specific about astrological influences. "
        "Include sections for different life areas. "
        "Do NOT use clichés like 'buckle up', 'wild ride', 'the universe has plans', or 'cosmic energy'. "
        "Write in a contemplative, slightly literary tone. "
        "Return ONLY valid JSON with this schema: "
        '{"title": "string", "body": "string (plain text, use \\n\\n for paragraphs)", '
        '"sections": [{"heading": "string", "body": "string"}], '
        '"word_count": number, "transit_highlights": ["string"]}'
    )

    user = f"""Generate a personalized daily horoscope for {date_context.isoformat()}.

NATAL CHART ({house_system} houses, {asc_str}):
{_format_natal_positions(natal_positions)}

Angles:
{chr(10).join(f"  {a['name']}: {a['degree']:.1f}° {a['sign']}" for a in natal_angles)}

CURRENT TRANSITS:
{_format_current_transits(current_transits)}

TRANSIT-TO-NATAL ASPECTS (today):
{_format_transit_aspects(transit_to_natal)}
{daily_ctx}
Write a 600-1000 word daily reading with sections for key life areas affected by today's transits.
Return ONLY the JSON object."""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
