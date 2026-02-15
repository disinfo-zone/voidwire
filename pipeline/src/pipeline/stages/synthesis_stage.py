"""Two-pass synthesis stage with fallback ladder."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import PromptTemplate
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
PLAN_TEMPLATE_CANDIDATES = ("synthesis_plan", "synthesis_plan_v1")
EVENT_PLAN_TEMPLATE_CANDIDATES = (
    "synthesis_plan_event",
    "synthesis_plan_event_v1",
    "starter_synthesis_event_plan",
)
PROSE_TEMPLATE_CANDIDATES = (
    "synthesis_prose",
    "synthesis_prose_v1",
    "starter_synthesis_prose",
)
EVENT_PROSE_TEMPLATE_CANDIDATES = (
    "synthesis_prose_event",
    "synthesis_prose_event_v1",
    "starter_synthesis_event_prose",
)
TEMPLATE_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _approx_tokens(text: str) -> int:
    # Lightweight heuristic for telemetry only; avoids tokenizer dependency at runtime.
    return max(1, int(round(len(text) / 4)))


def _record_prompt_metric(metrics: dict[str, dict[str, int]], key: str, prompt: str) -> None:
    metrics[key] = {
        "chars": len(prompt),
        "approx_tokens": _approx_tokens(prompt),
    }


def _truncate_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _prepare_signal_context(
    selected_signals: list[dict], *, limit: int = 20
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for signal in selected_signals[:limit]:
        if not isinstance(signal, dict):
            continue
        entities = signal.get("entities")
        compact_entities = (
            [str(entity).strip() for entity in entities if str(entity).strip()][:20]
            if isinstance(entities, list)
            else []
        )
        source_refs = signal.get("source_refs")
        compact_refs = (
            [str(ref).strip() for ref in source_refs if str(ref).strip()][:10]
            if isinstance(source_refs, list)
            else []
        )
        compact.append(
            {
                "id": str(signal.get("id", "")).strip(),
                "domain": str(signal.get("domain", "")).strip().lower(),
                "intensity": str(signal.get("intensity", "")).strip().lower(),
                "directionality": str(signal.get("directionality", "")).strip().lower(),
                "summary": _truncate_text(signal.get("summary", ""), 700),
                "entities": compact_entities,
                "source_refs": compact_refs,
                "was_wild_card": bool(signal.get("was_wild_card", False)),
                "selection_weight": signal.get("selection_weight"),
            }
        )
    return compact


def _prepare_thread_context(
    thread_snapshot: list[dict],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for thread in thread_snapshot[:limit]:
        if not isinstance(thread, dict):
            continue
        try:
            appearances = int(thread.get("appearances", 0) or 0)
        except (TypeError, ValueError):
            appearances = 0
        compact.append(
            {
                "id": str(thread.get("id", "")).strip(),
                "canonical_summary": _truncate_text(thread.get("canonical_summary", ""), 500),
                "domain": str(thread.get("domain", "")).strip().lower(),
                "appearances": appearances,
                "first_surfaced": thread.get("first_surfaced"),
                "last_seen": thread.get("last_seen"),
            }
        )
    return compact


def _collect_guarded_entities(selected_signals: list[dict], limit: int = 40) -> list[str]:
    stopwords = {
        "us",
        "we",
        "they",
        "them",
        "our",
        "their",
        "his",
        "her",
        "its",
        "you",
        "it",
        "government",
        "state",
        "country",
        "market",
        "economy",
    }
    seen: set[str] = set()
    ordered: list[str] = []
    for signal in selected_signals or []:
        for raw in signal.get("entities", []) or []:
            entity = str(raw).strip()
            if not entity:
                continue
            lowered = entity.lower()
            if lowered in stopwords:
                continue
            if len(entity) < 4 and " " not in entity:
                continue
            if lowered in seen:
                continue
            seen.add(lowered)
            ordered.append(entity)
            if len(ordered) >= limit:
                return ordered
    return ordered


def _derive_mention_policy(
    interpretive_plan: dict | None,
    selected_signals: list[dict],
    guarded_entities: list[str],
) -> dict[str, Any]:
    base = {
        "explicit_allowed": False,
        "explicit_budget": 0,
        "allowed_entities": [],
        "rationale": "Allusion-first default: explicit references disabled.",
    }
    if not isinstance(interpretive_plan, dict):
        return base

    candidate = interpretive_plan.get("mention_policy")
    if not isinstance(candidate, dict):
        return base

    explicit_allowed = bool(candidate.get("explicit_allowed", False))
    try:
        explicit_budget = int(candidate.get("explicit_budget", 0))
    except Exception:
        explicit_budget = 0
    explicit_budget = max(0, min(explicit_budget, 1))

    allowed_raw = candidate.get("allowed_entities", [])
    allowed = [str(e).strip() for e in (allowed_raw or []) if str(e).strip()]
    guarded_by_key = {g.lower(): g for g in guarded_entities}
    allowed_intersection = []
    for entity in allowed:
        key = entity.lower()
        if key in guarded_by_key and guarded_by_key[key] not in allowed_intersection:
            allowed_intersection.append(guarded_by_key[key])

    if not explicit_allowed:
        return base
    if explicit_budget == 0 or not allowed_intersection:
        return base

    # Escalation gate: explicit naming only when at least one major signal exists.
    has_major = any(
        str(s.get("intensity", "")).lower() == "major" for s in (selected_signals or [])
    )
    if not has_major:
        return base

    return {
        "explicit_allowed": True,
        "explicit_budget": 1,
        "allowed_entities": allowed_intersection[:1],
        "rationale": str(candidate.get("rationale", "")).strip()
        or "Plan-approved explicit reference for a major, unavoidable signal.",
    }


def _compose_output_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    sr = data.get("standard_reading")
    if isinstance(sr, dict):
        parts.append(str(sr.get("title", "")))
        parts.append(str(sr.get("body", "")))

    er = data.get("extended_reading")
    if isinstance(er, dict):
        parts.append(str(er.get("title", "")))
        parts.append(str(er.get("subtitle", "")))
        for section in er.get("sections", []) or []:
            if isinstance(section, dict):
                parts.append(str(section.get("heading", "")))
                parts.append(str(section.get("body", "")))

    for ann in data.get("transit_annotations", []) or []:
        if isinstance(ann, dict):
            parts.append(str(ann.get("aspect", "")))
            parts.append(str(ann.get("gloss", "")))
            parts.append(str(ann.get("cultural_resonance", "")))
            parts.append(str(ann.get("temporal_arc", "")))

    return " ".join(part for part in parts if part).strip()


def _count_entity_mentions(text_lower: str, entity: str) -> int:
    if not entity:
        return 0
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(entity.lower())}(?![a-z0-9])")
    return len(pattern.findall(text_lower))


def _is_mention_policy_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "guarded entities" in message
        or "direct references to guarded entities" in message
        or "explicit entity mention budget exceeded" in message
    )


def _template_usage(template: PromptTemplate) -> dict[str, Any]:
    return {
        "id": str(template.id),
        "template_name": str(template.template_name),
        "version": int(template.version),
    }


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


def _render_prompt_template(template_text: str, context: dict[str, Any]) -> str:
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


def _find_active_template(
    active_templates: dict[str, PromptTemplate],
    candidates: tuple[str, ...],
    prefix: str,
) -> PromptTemplate | None:
    for candidate in candidates:
        hit = active_templates.get(candidate.lower())
        if hit is not None:
            return hit

    prefix_lc = prefix.lower()
    prefix_matches = [tpl for name, tpl in active_templates.items() if name.startswith(prefix_lc)]
    if not prefix_matches:
        return None

    prefix_matches.sort(
        key=lambda tpl: (
            int(getattr(tpl, "version", 0) or 0),
            str(getattr(tpl, "template_name", "")),
        ),
        reverse=True,
    )
    return prefix_matches[0]


async def _load_active_templates(session: AsyncSession) -> dict[str, PromptTemplate]:
    result = await session.execute(select(PromptTemplate).where(PromptTemplate.is_active))
    active: dict[str, PromptTemplate] = {}
    for template in result.scalars().all():
        name = str(template.template_name).strip().lower()
        if not name:
            continue
        existing = active.get(name)
        if existing is None or int(template.version) >= int(existing.version):
            active[name] = template
    return active


async def run_synthesis_stage(
    ephemeris_data: dict,
    selected_signals: list[dict],
    thread_snapshot: list[dict],
    date_context: date,
    sky_only: bool,
    session: AsyncSession,
    settings: SynthesisSettings | None = None,
    allow_guard_relaxation: bool = False,
    event_context: dict[str, Any] | None = None,
) -> dict:
    ss = settings or SynthesisSettings()
    from pipeline.stages.distillation_stage import _get_llm_client

    fast_mode = allow_guard_relaxation
    # Event-linked runs should resolve quickly and avoid expensive repair loops.
    llm_timeout = 90.0 if fast_mode else 120.0
    client = await _get_llm_client(session, "synthesis", timeout=llm_timeout)

    prompt_payloads = {}
    template_versions: dict[str, Any] = {}
    try:
        active_templates = await _load_active_templates(session)
    except Exception as exc:
        logger.warning("Could not load active prompt templates, using code defaults: %s", exc)
        active_templates = {}

    prompt_signals = _prepare_signal_context(
        selected_signals or [],
        limit=max(1, int(ss.signal_display_limit)),
    )
    prompt_threads = _prepare_thread_context(
        thread_snapshot or [],
        limit=max(1, int(ss.thread_display_limit)),
    )
    prompt_metrics: dict[str, dict[str, int]] = {}
    prompt_payloads["context_stats"] = {
        "signals": len(prompt_signals),
        "threads": len(prompt_threads),
    }
    prompt_payloads["_telemetry"] = {
        "context": {
            "signals_used": len(prompt_signals),
            "threads_used": len(prompt_threads),
            "signal_display_limit": int(ss.signal_display_limit),
            "thread_display_limit": int(ss.thread_display_limit),
        },
        "prompts": prompt_metrics,
        "mode": "event_fast_mode" if fast_mode else "default",
        "llm_timeout_seconds": int(llm_timeout),
    }
    if isinstance(event_context, dict) and event_context:
        prompt_payloads["_telemetry"]["event_context"] = {
            "id": str(event_context.get("id", "")).strip(),
            "event_type": str(event_context.get("event_type", "")).strip(),
            "days_out": event_context.get("days_out"),
        }
    logger.info(
        "Synthesis stage start date=%s fast_mode=%s sky_only=%s signals=%d threads=%d llm_timeout=%ss event=%s",
        date_context,
        fast_mode,
        sky_only,
        len(prompt_signals),
        len(prompt_threads),
        int(llm_timeout),
        str(event_context.get("event_type", "")).strip() if isinstance(event_context, dict) else "",
    )

    # Pass A: Interpretive plan (with retry at tweaked temperature)
    interpretive_plan = None
    if fast_mode:
        prompt_payloads["pass_a_skipped"] = "event_fast_mode"
    else:
        plan_template = None
        if isinstance(event_context, dict) and event_context:
            plan_template = _find_active_template(
                active_templates,
                EVENT_PLAN_TEMPLATE_CANDIDATES,
                prefix="synthesis_plan_event",
            )
        elif plan_template is None:
            plan_template = _find_active_template(
                active_templates,
                PLAN_TEMPLATE_CANDIDATES,
                prefix="synthesis_plan",
            )
        if plan_template is not None:
            plan_prompt = _render_prompt_template(
                plan_template.content,
                {
                    "date_context": date_context,
                    "ephemeris_data": ephemeris_data,
                    "event_context": event_context or {},
                    "selected_signals": prompt_signals,
                    "signals": prompt_signals,
                    "thread_snapshot": prompt_threads,
                    "sky_only": sky_only,
                },
            )
            usage = _template_usage(plan_template)
            plan_key = (
                "synthesis_plan_event"
                if "event" in str(plan_template.template_name).lower()
                else "synthesis_plan"
            )
            template_versions[plan_key] = usage
            prompt_payloads["pass_a_template"] = usage
        else:
            plan_prompt = build_plan_prompt(
                ephemeris_data,
                prompt_signals,
                prompt_threads,
                date_context,
                event_context=event_context,
                sky_only=sky_only,
                thread_display_limit=ss.thread_display_limit,
            )
        _record_prompt_metric(prompt_metrics, "pass_a", plan_prompt)
        prompt_payloads["pass_a"] = plan_prompt
        for attempt in range(ss.plan_retries):
            try:
                temp = ss.plan_temp_start + (attempt * ss.plan_temp_step)
                logger.info(
                    "Synthesis pass_a attempt=%d temp=%.2f",
                    attempt + 1,
                    temp,
                )
                interpretive_plan = await generate_with_validation(
                    client,
                    "synthesis",
                    [{"role": "user", "content": plan_prompt}],
                    _validate_plan,
                    temperature=temp,
                )
                break
            except asyncio.CancelledError:
                logger.warning("Synthesis pass_a cancelled at attempt=%d", attempt + 1)
                await client.close()
                raise
            except Exception as e:
                logger.warning("Pass A attempt %d failed: %s", attempt + 1, e)

    guarded_entities = _collect_guarded_entities(prompt_signals)
    mention_policy = _derive_mention_policy(interpretive_plan, prompt_signals, guarded_entities)

    # Pass B: Prose generation (retries with decreasing temperature)
    prose_template = None
    if isinstance(event_context, dict) and event_context:
        prose_template = _find_active_template(
            active_templates,
            EVENT_PROSE_TEMPLATE_CANDIDATES,
            prefix="synthesis_prose_event",
        )
    elif prose_template is None:
        prose_template = _find_active_template(
            active_templates,
            PROSE_TEMPLATE_CANDIDATES,
            prefix="synthesis_prose",
        )
    if prose_template is not None:
        prose_prompt = _render_prompt_template(
            prose_template.content,
            {
                "date_context": date_context,
                "ephemeris_data": ephemeris_data,
                "event_context": event_context or {},
                "selected_signals": prompt_signals,
                "signals": prompt_signals,
                "thread_snapshot": prompt_threads,
                "interpretive_plan": interpretive_plan or {},
                "mention_policy": mention_policy,
                "explicit_entity_guard": guarded_entities,
                "guarded_entities": guarded_entities,
                "sky_only": sky_only,
                "standard_word_range": ss.standard_word_range,
                "extended_word_range": ss.extended_word_range,
                "banned_phrases": ss.banned_phrases,
            },
        )
        usage = _template_usage(prose_template)
        prose_key = (
            "synthesis_prose_event"
            if "event" in str(prose_template.template_name).lower()
            else "synthesis_prose"
        )
        template_versions[prose_key] = usage
        prompt_payloads["pass_b_template"] = usage
    else:
        prose_prompt = build_prose_prompt(
            ephemeris_data,
            prompt_signals,
            prompt_threads,
            date_context,
            event_context,
            interpretive_plan,
            mention_policy,
            guarded_entities,
            sky_only,
            standard_word_range=ss.standard_word_range,
            extended_word_range=ss.extended_word_range,
            banned_phrases=ss.banned_phrases,
            thread_display_limit=ss.thread_display_limit,
        )
    _record_prompt_metric(prompt_metrics, "pass_b", prose_prompt)
    prompt_payloads["pass_b"] = prose_prompt

    prose_retries = 1 if fast_mode else ss.prose_retries
    result = None
    relaxed_guard_used = False
    for attempt in range(prose_retries):
        temperature = max(ss.prose_temp_min, ss.prose_temp_start - attempt * ss.prose_temp_step)
        try:
            validate_fn = (
                _validate_prose_structure
                if fast_mode
                else lambda data: _validate_prose(
                    data,
                    mention_policy=mention_policy,
                    guarded_entities=guarded_entities,
                )
            )
            logger.info(
                "Synthesis pass_b attempt=%d temp=%.2f repair_retry=%s",
                attempt + 1,
                temperature,
                not fast_mode,
            )
            result = await generate_with_validation(
                client,
                "synthesis",
                [{"role": "user", "content": prose_prompt}],
                validate_fn,
                temperature=temperature,
                repair_retry=not fast_mode,
            )
            break
        except asyncio.CancelledError:
            logger.warning("Synthesis pass_b cancelled at attempt=%d", attempt + 1)
            await client.close()
            raise
        except Exception as e:
            logger.warning("Pass B attempt %d failed: %s", attempt + 1, e)
            if allow_guard_relaxation and not relaxed_guard_used and _is_mention_policy_error(e):
                relaxed_guard_used = True
                prompt_payloads["guard_policy_relaxed"] = {
                    "reason": str(e),
                    "attempt": attempt + 1,
                }
                logger.warning(
                    "Pass B guard policy failed; retrying once with structure-only validation"
                )
                try:
                    logger.info(
                        "Synthesis pass_b relaxed_validation attempt=%d temp=%.2f",
                        attempt + 1,
                        temperature,
                    )
                    result = await generate_with_validation(
                        client,
                        "synthesis",
                        [{"role": "user", "content": prose_prompt}],
                        _validate_prose_structure,
                        temperature=temperature,
                        repair_retry=False,
                    )
                    break
                except asyncio.CancelledError:
                    logger.warning(
                        "Synthesis pass_b relaxed validation cancelled at attempt=%d",
                        attempt + 1,
                    )
                    await client.close()
                    raise
                except Exception as relaxed_exc:
                    logger.warning("Pass B relaxed validation attempt failed: %s", relaxed_exc)
                    # Move directly to sky-only fallback instead of exhausting retries.
                    break

    # Fallback: sky-only retry if full synthesis failed but we have ephemeris
    if result is None and not sky_only:
        logger.warning("Full synthesis failed, falling back to sky-only mode")
        fallback_policy = {"explicit_allowed": False, "explicit_budget": 0, "allowed_entities": []}
        if prose_template is not None:
            sky_prompt = _render_prompt_template(
                prose_template.content,
                {
                    "date_context": date_context,
                    "ephemeris_data": ephemeris_data,
                    "event_context": event_context or {},
                    "selected_signals": [],
                    "signals": [],
                    "thread_snapshot": prompt_threads,
                    "interpretive_plan": interpretive_plan or {},
                    "mention_policy": fallback_policy,
                    "explicit_entity_guard": [],
                    "guarded_entities": [],
                    "sky_only": True,
                    "standard_word_range": ss.standard_word_range,
                    "extended_word_range": ss.extended_word_range,
                    "banned_phrases": ss.banned_phrases,
                },
            )
        else:
            sky_prompt = build_prose_prompt(
                ephemeris_data,
                [],
                prompt_threads,
                date_context,
                event_context,
                interpretive_plan,
                fallback_policy,
                [],
                sky_only=True,
                standard_word_range=ss.standard_word_range,
                extended_word_range=ss.extended_word_range,
                banned_phrases=ss.banned_phrases,
                thread_display_limit=ss.thread_display_limit,
            )
        _record_prompt_metric(prompt_metrics, "pass_b_fallback", sky_prompt)
        prompt_payloads["pass_b_fallback"] = sky_prompt
        try:
            logger.info(
                "Synthesis pass_b fallback temp=%.2f repair_retry=%s",
                ss.fallback_temp,
                not fast_mode,
            )
            result = await generate_with_validation(
                client,
                "synthesis",
                [{"role": "user", "content": sky_prompt}],
                _validate_prose_structure
                if fast_mode
                else lambda data: _validate_prose(
                    data,
                    mention_policy=fallback_policy,
                    guarded_entities=[],
                ),
                temperature=ss.fallback_temp,
                repair_retry=not fast_mode,
            )
        except asyncio.CancelledError:
            logger.warning("Synthesis pass_b fallback cancelled")
            await client.close()
            raise
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
            "template_versions": template_versions,
            "ephemeris_data": ephemeris_data,
        }

    return {
        "standard_reading": result.get("standard_reading", {}),
        "extended_reading": result.get(
            "extended_reading", {"title": "", "subtitle": "", "sections": [], "word_count": 0}
        ),
        "annotations": result.get("transit_annotations", []),
        "interpretive_plan": interpretive_plan,
        "generated_output": result,
        "prompt_payloads": prompt_payloads,
        "template_versions": template_versions,
    }


def _validate_plan(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("Plan must be a JSON object")
    if "title" not in data:
        raise ValueError("Plan must have 'title'")
    if "aspect_readings" not in data:
        raise ValueError("Plan must have 'aspect_readings'")


def _validate_prose(
    data: Any,
    *,
    mention_policy: dict | None = None,
    guarded_entities: list[str] | None = None,
) -> None:
    _validate_prose_structure(data)
    policy = mention_policy or {}
    explicit_allowed = bool(policy.get("explicit_allowed", False))
    try:
        explicit_budget = int(policy.get("explicit_budget", 0))
    except Exception:
        explicit_budget = 0
    explicit_budget = max(0, min(explicit_budget, 1))
    if not explicit_allowed:
        explicit_budget = 0

    allowed_entities = {
        str(e).strip().lower() for e in (policy.get("allowed_entities", []) or []) if str(e).strip()
    }
    guarded = [str(e).strip() for e in (guarded_entities or []) if str(e).strip()]
    if not guarded:
        return

    output_text = _compose_output_text(data)
    lowered = output_text.lower()

    forbidden_hits: list[str] = []
    allowed_mentions = 0
    for entity in guarded:
        mentions = _count_entity_mentions(lowered, entity)
        if mentions <= 0:
            continue
        if entity.lower() in allowed_entities:
            allowed_mentions += mentions
        else:
            forbidden_hits.append(entity)

    if forbidden_hits:
        sample = ", ".join(dict.fromkeys(forbidden_hits).keys())
        raise ValueError(f"Direct references to guarded entities are not allowed: {sample}")
    if allowed_mentions > explicit_budget:
        raise ValueError(
            f"Explicit entity mention budget exceeded: allowed {explicit_budget}, found {allowed_mentions}"
        )


def _validate_prose_structure(data: Any) -> None:
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
