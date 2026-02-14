"""Two-pass synthesis stage with fallback ladder."""
from __future__ import annotations
import logging
from datetime import date
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.services.llm_client import generate_with_validation
from voidwire.services.pipeline_settings import SynthesisSettings
from pipeline.prompts.synthesis_plan import build_plan_prompt
from pipeline.prompts.synthesis_prose import build_prose_prompt

logger = logging.getLogger(__name__)

SILENCE_READING = {
    "title": "The Signal Obscured",
    "body": "The signal is obscured. The planetary mechanism grinds on, silent and unobserved.",
    "word_count": 14,
}


async def run_synthesis_stage(
    ephemeris_data: dict,
    selected_signals: list[dict],
    thread_snapshot: list[dict],
    date_context: date,
    sky_only: bool,
    session: AsyncSession,
    settings: SynthesisSettings | None = None,
) -> dict:
    ss = settings or SynthesisSettings()
    from pipeline.stages.distillation_stage import _get_llm_client
    client = await _get_llm_client(session, "synthesis")

    prompt_payloads = {}

    # Pass A: Interpretive plan (with retry at tweaked temperature)
    plan_prompt = build_plan_prompt(ephemeris_data, selected_signals, thread_snapshot, date_context, sky_only, thread_display_limit=ss.thread_display_limit)
    prompt_payloads["pass_a"] = plan_prompt

    interpretive_plan = None
    for attempt in range(ss.plan_retries):
        try:
            temp = ss.plan_temp_start + (attempt * ss.plan_temp_step)
            interpretive_plan = await generate_with_validation(
                client, "synthesis",
                [{"role": "user", "content": plan_prompt}],
                _validate_plan,
                temperature=temp,
            )
            break
        except Exception as e:
            logger.warning("Pass A attempt %d failed: %s", attempt + 1, e)

    # Pass B: Prose generation (retries with decreasing temperature)
    prose_prompt = build_prose_prompt(
        ephemeris_data, selected_signals, thread_snapshot,
        date_context, interpretive_plan, sky_only,
        standard_word_range=ss.standard_word_range,
        extended_word_range=ss.extended_word_range,
        banned_phrases=ss.banned_phrases,
        thread_display_limit=ss.thread_display_limit,
    )
    prompt_payloads["pass_b"] = prose_prompt

    result = None
    for attempt in range(ss.prose_retries):
        try:
            result = await generate_with_validation(
                client, "synthesis",
                [{"role": "user", "content": prose_prompt}],
                _validate_prose,
                temperature=max(ss.prose_temp_min, ss.prose_temp_start - attempt * ss.prose_temp_step),
            )
            break
        except Exception as e:
            logger.warning("Pass B attempt %d failed: %s", attempt + 1, e)

    # Fallback: sky-only retry if full synthesis failed but we have ephemeris
    if result is None and not sky_only:
        logger.warning("Full synthesis failed, falling back to sky-only mode")
        sky_prompt = build_prose_prompt(
            ephemeris_data, [], thread_snapshot,
            date_context, interpretive_plan, sky_only=True,
            standard_word_range=ss.standard_word_range,
            extended_word_range=ss.extended_word_range,
            banned_phrases=ss.banned_phrases,
            thread_display_limit=ss.thread_display_limit,
        )
        prompt_payloads["pass_b_fallback"] = sky_prompt
        try:
            result = await generate_with_validation(
                client, "synthesis",
                [{"role": "user", "content": sky_prompt}],
                _validate_prose,
                temperature=ss.fallback_temp,
            )
        except Exception as e:
            logger.warning("Sky-only fallback failed: %s", e)

    await client.close()

    if result is None:
        # Final fallback: silence reading (still includes ephemeris context)
        return {
            "standard_reading": SILENCE_READING,
            "extended_reading": {"title": "", "subtitle": "", "sections": [], "word_count": 0},
            "annotations": [],
            "interpretive_plan": interpretive_plan,
            "generated_output": None,
            "prompt_payloads": prompt_payloads,
            "ephemeris_data": ephemeris_data,
        }

    return {
        "standard_reading": result.get("standard_reading", {}),
        "extended_reading": result.get("extended_reading", {"title": "", "subtitle": "", "sections": [], "word_count": 0}),
        "annotations": result.get("transit_annotations", []),
        "interpretive_plan": interpretive_plan,
        "generated_output": result,
        "prompt_payloads": prompt_payloads,
    }


def _validate_plan(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("Plan must be a JSON object")
    if "title" not in data:
        raise ValueError("Plan must have 'title'")
    if "aspect_readings" not in data:
        raise ValueError("Plan must have 'aspect_readings'")


def _validate_prose(data: Any) -> None:
    if not isinstance(data, dict) or "standard_reading" not in data:
        raise ValueError("Missing standard_reading")
    sr = data["standard_reading"]
    if not isinstance(sr, dict) or "title" not in sr or "body" not in sr:
        raise ValueError("standard_reading needs title and body")
    body = sr.get("body", "")
    word_count = len(body.split())
    # Word count soft check (warn but don't reject)
    if word_count < 100:
        logger.warning("Standard reading body only %d words (target: 200-400)", word_count)
