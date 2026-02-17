"""Celestial weather description generation and caching service."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import LLMConfig, PipelineRun
from voidwire.services.llm_client import (
    LLMClient,
    LLMSlotConfig,
    generate_with_validation,
    has_non_latin,
)
from voidwire.services.prompt_template_runtime import (
    load_active_prompt_template,
    render_prompt_template,
)

from api.services.site_config import load_site_config

logger = logging.getLogger(__name__)

_SLOT_NAME = "personal_free"


def _validate_weather_json(data: dict) -> dict:
    """Validate weather description JSON has expected keys."""
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    for key in ("moon_phase", "void_of_course"):
        if key not in data:
            raise ValueError(f"Missing required key: {key}")
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f"Key '{key}' must be a non-empty string")
    # retrogrades can be null or a string
    retro = data.get("retrogrades")
    if retro is not None and not isinstance(retro, str):
        raise ValueError("'retrogrades' must be a string or null")
    # timeline must be a list of strings if present
    timeline = data.get("timeline")
    if timeline is not None:
        if not isinstance(timeline, list):
            raise ValueError("'timeline' must be a list of strings")
        for i, item in enumerate(timeline):
            if not isinstance(item, str):
                raise ValueError(f"'timeline[{i}]' must be a string")
    return data


def _has_non_latin_values(data: dict) -> bool:
    """Check if any string values contain non-Latin characters."""
    for value in data.values():
        if isinstance(value, str) and has_non_latin(value):
            return True
    return False


def _format_ephemeris_summary(ephemeris: dict) -> str:
    """Build a compact text summary of ephemeris data for the LLM prompt."""
    parts: list[str] = []

    positions = ephemeris.get("positions", {})
    if isinstance(positions, list):
        positions = {p.get("body", f"body_{i}"): p for i, p in enumerate(positions)}
    for body, pos in positions.items():
        if isinstance(pos, dict):
            sign = pos.get("sign", "?")
            deg = pos.get("degree", "?")
            retro = " Rx" if pos.get("retrograde") else ""
            parts.append(f"{body}: {deg}° {sign}{retro}")

    lunar = ephemeris.get("lunar", {})
    if lunar:
        phase = lunar.get("phase_name", "?")
        pct = lunar.get("phase_pct", 0)
        illumination = round((1 - math.cos(pct * 2 * math.pi)) / 2 * 100)
        voc = "VOC active" if lunar.get("void_of_course") else "VOC clear"
        parts.append(f"Moon phase: {phase} ({illumination}% illuminated), {voc}")

    aspects = ephemeris.get("aspects", [])
    if aspects:
        aspect_lines = []
        for a in aspects[:10]:
            if isinstance(a, dict):
                desc = a.get("aspect") or f"{a.get('body1', '?')} {a.get('type', '?')} {a.get('body2', '?')}"
                aspect_lines.append(str(desc))
        if aspect_lines:
            parts.append("Key aspects: " + "; ".join(aspect_lines))

    # Timeline events for LLM descriptions
    timeline_entries: list[str] = []
    idx = 1
    for si in ephemeris.get("stations_and_ingresses", []):
        if isinstance(si, dict):
            label = si.get("type", "event")
            body = si.get("body", "")
            sign = si.get("sign", "")
            at = si.get("at", "")
            date_part = at[:10] if at else ""
            desc = f"{label}: {body}"
            if sign:
                desc += f" in {sign}"
            if date_part:
                desc += f" ({date_part})"
            timeline_entries.append(f"{idx}. {desc}")
            idx += 1
    for fe in ephemeris.get("forward_ephemeris", []):
        if isinstance(fe, dict):
            event_desc = fe.get("event", "")
            at = fe.get("at", "")
            date_part = at[:10] if at else ""
            desc = event_desc
            if date_part:
                desc += f" ({date_part})"
            timeline_entries.append(f"{idx}. {desc}")
            idx += 1
    if timeline_entries:
        parts.append("Timeline events (write one description per event):\n" + "\n".join(timeline_entries))

    return "\n".join(parts)


async def _get_today_run(db: AsyncSession) -> PipelineRun | None:
    """Get today's completed pipeline run."""
    config = await load_site_config(db)
    tz_name = str(config.get("timezone", "UTC")).strip() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = UTC
    today = datetime.now(tz).date()

    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.date_context == today, PipelineRun.status == "completed")
        .order_by(PipelineRun.run_number.desc())
    )
    return result.scalars().first()


async def _build_llm_client(db: AsyncSession) -> LLMClient | None:
    """Build an LLM client configured for the personal_free slot."""
    result = await db.execute(
        select(LLMConfig).where(LLMConfig.slot == _SLOT_NAME, LLMConfig.is_active)
    )
    config = result.scalars().first()
    if not config:
        logger.warning("LLM slot '%s' not configured or inactive", _SLOT_NAME)
        return None

    client = LLMClient()
    client.configure_slot(
        LLMSlotConfig(
            slot=config.slot,
            provider_name=config.provider_name,
            api_endpoint=config.api_endpoint,
            model_id=config.model_id,
            api_key_encrypted=config.api_key_encrypted,
            max_tokens=config.max_tokens,
            temperature=config.temperature or 0.7,
            extra_params=config.extra_params or {},
        )
    )
    return client


async def get_or_generate_weather(db: AsyncSession) -> dict | None:
    """Get or generate celestial weather descriptions for today."""
    run = await _get_today_run(db)
    if not run or not run.ephemeris_json:
        return None

    ephemeris = run.ephemeris_json
    if not isinstance(ephemeris, dict):
        return None

    # Check cache
    cached = ephemeris.get("weather_descriptions")
    if isinstance(cached, dict) and cached.get("moon_phase"):
        return cached

    # Build LLM client
    client = await _build_llm_client(db)
    if not client:
        return None

    # Ensure latest template version is available
    from api.services.template_defaults import ensure_starter_prompt_template

    await ensure_starter_prompt_template(db)

    # Load template
    template = await load_active_prompt_template(
        db,
        candidates=["starter_celestial_weather"],
        prefix="celestial_weather",
    )
    if not template:
        logger.warning("No celestial weather template found")
        return None

    # Build context
    config = await load_site_config(db)
    tz_name = str(config.get("timezone", "UTC")).strip() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = UTC
    today = datetime.now(tz)

    context = {
        "date_context": today.strftime("%A, %B %d, %Y"),
        "ephemeris_data": _format_ephemeris_summary(ephemeris),
    }
    prompt_text = render_prompt_template(str(template.content), context)
    messages = [{"role": "user", "content": prompt_text}]

    try:
        content = await generate_with_validation(
            client, _SLOT_NAME, messages, _validate_weather_json
        )
    except Exception:
        logger.exception("Failed to generate weather descriptions")
        return None

    # Non-latin check with one retry
    if _has_non_latin_values(content):
        logger.warning("Non-Latin characters in weather output, retrying")
        retry_messages = [
            {"role": "user", "content": prompt_text + "\n\nIMPORTANT: Write in English only. Use only Latin characters."},
        ]
        try:
            content = await generate_with_validation(
                client, _SLOT_NAME, retry_messages, _validate_weather_json
            )
        except Exception:
            logger.warning("Retry also failed, using first attempt")

    # Cache in ephemeris_json
    ephemeris["weather_descriptions"] = content
    run.ephemeris_json = ephemeris
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(run, "ephemeris_json")
    await db.commit()

    return content


async def regenerate_weather(db: AsyncSession) -> dict | None:
    """Clear cached weather descriptions and regenerate them."""
    run = await _get_today_run(db)
    if not run or not run.ephemeris_json:
        return None

    ephemeris = run.ephemeris_json
    if not isinstance(ephemeris, dict):
        return None

    # Clear existing cache
    ephemeris.pop("weather_descriptions", None)
    run.ephemeris_json = ephemeris
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(run, "ephemeris_json")
    await db.commit()

    return await get_or_generate_weather(db)
