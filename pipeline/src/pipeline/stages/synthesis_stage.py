"""Two-pass synthesis stage."""
from __future__ import annotations
import logging
from datetime import date
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.services.llm_client import generate_with_validation
from pipeline.prompts.synthesis_plan import build_plan_prompt
from pipeline.prompts.synthesis_prose import build_prose_prompt

logger = logging.getLogger(__name__)

async def run_synthesis_stage(ephemeris_data: dict, selected_signals: list[dict], thread_snapshot: list[dict], date_context: date, sky_only: bool, session: AsyncSession) -> dict:
    from pipeline.stages.distillation_stage import _get_llm_client
    client = await _get_llm_client(session, "synthesis")
    prompt_payloads = {}
    plan_prompt = build_plan_prompt(ephemeris_data, selected_signals, thread_snapshot, date_context, sky_only)
    prompt_payloads["pass_a"] = plan_prompt
    interpretive_plan = None
    try:
        interpretive_plan = await generate_with_validation(client, "synthesis", [{"role":"user","content":plan_prompt}], lambda d: None if isinstance(d, dict) and "title" in d else (_ for _ in ()).throw(ValueError("Plan must have title")), temperature=0.7)
    except Exception as e:
        logger.warning("Pass A failed: %s", e)
    prose_prompt = build_prose_prompt(ephemeris_data, selected_signals, thread_snapshot, date_context, interpretive_plan, sky_only)
    prompt_payloads["pass_b"] = prose_prompt
    result = None
    for attempt in range(3):
        try:
            def _validate(d):
                if not isinstance(d, dict) or "standard_reading" not in d:
                    raise ValueError("Missing standard_reading")
                sr = d["standard_reading"]
                if not isinstance(sr, dict) or "title" not in sr or "body" not in sr:
                    raise ValueError("standard_reading needs title and body")
            result = await generate_with_validation(client, "synthesis", [{"role":"user","content":prose_prompt}], _validate, temperature=max(0.5, 0.7-attempt*0.1))
            break
        except Exception as e:
            logger.warning("Pass B attempt %d failed: %s", attempt+1, e)
    await client.close()
    if result is None:
        return {"standard_reading": {"title":"The Signal Obscured","body":"The signal is obscured. The planetary mechanism grinds on, silent and unobserved.","word_count":14}, "extended_reading": {"title":"","subtitle":"","sections":[],"word_count":0}, "annotations": [], "interpretive_plan": interpretive_plan, "generated_output": None, "prompt_payloads": prompt_payloads}
    return {"standard_reading": result.get("standard_reading",{}), "extended_reading": result.get("extended_reading",{"title":"","subtitle":"","sections":[],"word_count":0}), "annotations": result.get("transit_annotations",[]), "interpretive_plan": interpretive_plan, "generated_output": result, "prompt_payloads": prompt_payloads}
