"""Batch generation of free-tier weekly personal readings.

Standalone entry point — manages its own DB session, does not go through the
orchestrator.  Same 3-phase concurrent pattern as the pro batch stage.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, date, datetime, timedelta

from ephemeris import calculate_day
from ephemeris.natal import calculate_natal_chart, calculate_transit_to_natal_aspects
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from voidwire.database import get_session
from voidwire.models import (
    BatchRun,
    LLMConfig,
    PersonalReading,
    Subscription,
    User,
    UserProfile,
)
from voidwire.services.llm_client import (
    LLMClient,
    LLMSlotConfig,
    fix_non_latin_content,
    generate_with_validation,
)
from voidwire.services.pipeline_settings import load_pipeline_settings
from voidwire.services.prompt_template_runtime import (
    load_active_prompt_template,
    template_usage,
)

from pipeline.prompts.personal_reading import (
    PERSONAL_READING_FREE_TEMPLATE_PREFIX,
    build_free_reading_prompt,
    resolve_personal_template_candidates,
)

logger = logging.getLogger(__name__)

_BATCH_CONCURRENCY = 50


# ---------------------------------------------------------------------------
# Helpers (duplicated from personal_reading_service to keep batch standalone)
# ---------------------------------------------------------------------------

def _current_week_key(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_bounds(d: date) -> tuple[date, date]:
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def _upcoming_monday(d: date) -> date:
    """Return d if it's already Monday, else advance to the next Monday."""
    days_ahead = (0 - d.weekday()) % 7  # Monday = 0
    return d if days_ahead == 0 else d + timedelta(days=days_ahead)


def _normalize_transit_positions(raw_positions: object) -> dict[str, dict]:
    if not isinstance(raw_positions, dict):
        return {}
    normalized: dict[str, dict] = {}
    for body_name, payload in raw_positions.items():
        if hasattr(payload, "model_dump"):
            data = payload.model_dump()
        elif isinstance(payload, dict):
            data = dict(payload)
        else:
            continue
        try:
            longitude = float(data.get("longitude"))
        except (TypeError, ValueError):
            continue
        normalized[str(body_name)] = {
            "longitude": longitude,
            "sign": str(data.get("sign", "")),
            "degree": float(data.get("degree", 0.0) or 0.0),
            "speed_deg_day": float(data.get("speed_deg_day", 0.0) or 0.0),
            "retrograde": bool(data.get("retrograde", False)),
        }
    return normalized


def _aspect_sort_key(aspect: dict) -> tuple[int, float, str]:
    significance_rank = {
        "major": 0,
        "moderate": 1,
        "minor": 2,
    }.get(str(aspect.get("significance", "")).lower(), 3)
    try:
        orb = float(aspect.get("orb_degrees", 99.0))
    except (TypeError, ValueError):
        orb = 99.0
    day = str(aspect.get("date", ""))
    return (significance_rank, orb, day)


def _aggregate_weekly_aspects(aspects: list[dict], *, limit: int = 20) -> list[dict]:
    by_signature: dict[tuple[str, str, str], dict] = {}
    for aspect in aspects:
        signature = (
            str(aspect.get("transit_body", "")),
            str(aspect.get("type", "")),
            str(aspect.get("natal_body", "")),
        )
        existing = by_signature.get(signature)
        if existing is None or _aspect_sort_key(aspect) < _aspect_sort_key(existing):
            by_signature[signature] = aspect
    deduped = list(by_signature.values())
    deduped.sort(key=_aspect_sort_key)
    return deduped[:limit]


def _normalize_word_range(value: object, fallback: tuple[int, int]) -> list[int]:
    if isinstance(value, list) and len(value) == 2:
        try:
            low = int(value[0])
            high = int(value[1])
            if low > 0 and high >= low:
                return [low, high]
        except (TypeError, ValueError):
            pass
    return [fallback[0], fallback[1]]


def _validate_reading_json(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    if "title" not in data or "body" not in data:
        raise ValueError("Missing required fields: title, body")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_free_reading_batch(target_date: date | None = None) -> int:
    """Generate free weekly readings for all eligible non-pro users.

    Returns the number of readings generated.
    """
    today = target_date if target_date is not None else _upcoming_monday(date.today())
    week_key = _current_week_key(today)
    week_start, week_end = _week_bounds(today)

    # -- Create BatchRun record in its own session so it persists on failure --
    batch_started = datetime.now(UTC)
    batch_run_id = None
    try:
        async with get_session() as br_session:
            batch_run = BatchRun(
                batch_type="free_reading",
                started_at=batch_started,
                status="running",
                target_date=today,
                week_key=week_key,
            )
            br_session.add(batch_run)
            await br_session.flush()
            batch_run_id = batch_run.id
    except Exception:
        logger.warning("Could not create BatchRun record", exc_info=True)

    eligible_count = 0
    skipped_count = 0
    gen_count = 0
    error_count = 0
    non_latin_fix_count = 0
    elapsed_times: list[float] = []
    template_version_str = ""

    try:
        async with get_session() as session:
            # ---- Pre-checks ----
            result = await session.execute(
                select(LLMConfig).where(
                    LLMConfig.slot == "personal_free", LLMConfig.is_active
                )
            )
            llm_config = result.scalars().first()
            if not llm_config:
                logger.info("personal_free LLM slot not configured; skipping free batch")
                return 0

            pipeline_settings = await load_pipeline_settings(session)
            personal_settings = pipeline_settings.personal
            if not bool(personal_settings.enabled):
                logger.info("personal readings disabled via pipeline settings; skipping free batch")
                return 0

            # ---- Identify free users (active, has profile, not pro, no pro_override) ----
            pro_sub_ids = select(Subscription.user_id).where(
                Subscription.status.in_(("active", "trialing"))
            )
            result = await session.execute(
                select(User, UserProfile)
                .join(UserProfile, UserProfile.user_id == User.id)
                .where(
                    User.is_active,
                    User.pro_override.is_(False),
                    User.id.notin_(pro_sub_ids),
                )
            )
            user_profile_pairs: list[tuple[User, UserProfile]] = list(result.all())

            # Deduplicate by user_id
            deduped: dict[object, tuple[User, UserProfile]] = {}
            for user, profile in user_profile_pairs:
                deduped.setdefault(user.id, (user, profile))
            free_users = list(deduped.values())

            if not free_users:
                logger.info("No eligible free users with profiles; skipping free batch")
                return 0

            eligible_count = len(free_users)

            # ---- Skip users who already have a reading this week ----
            existing_result = await session.execute(
                select(PersonalReading.user_id).where(
                    PersonalReading.tier == "free",
                    PersonalReading.week_key == week_key,
                )
            )
            existing_user_ids = set(existing_result.scalars().all())
            free_users = [
                (u, p) for u, p in free_users if u.id not in existing_user_ids
            ]
            skipped_count = eligible_count - len(free_users)

            if not free_users:
                logger.info("All free users already have readings for %s; nothing to do", week_key)
                return 0

            # ---- Phase 1: Prep (sequential, DB-bound) ----

            # Pre-compute transit positions for every day of the week (shared across all users)
            weekly_transits: dict[date, dict[str, dict]] = {}
            day = week_start
            while day <= week_end:
                generated = await calculate_day(day, db_session=session)
                weekly_transits[day] = _normalize_transit_positions(generated.positions)
                day += timedelta(days=1)

            # Use today's transits as the "current transits" context
            today_transits = weekly_transits.get(today) or weekly_transits.get(week_start, {})

            # Load settings / template once
            blocked_words = [
                str(phrase).strip()
                for phrase in (pipeline_settings.synthesis.banned_phrases or [])
                if str(phrase).strip()
            ]
            free_word_range = _normalize_word_range(
                personal_settings.free_word_range, (300, 500)
            )
            weekly_aspect_limit = max(5, min(60, int(personal_settings.weekly_aspect_limit or 20)))

            free_candidates = resolve_personal_template_candidates(
                "free", personal_settings.free_template_name
            )
            template = await load_active_prompt_template(
                session,
                candidates=free_candidates,
                prefix=PERSONAL_READING_FREE_TEMPLATE_PREFIX,
            )
            template_version_str = (
                f"{template.template_name}.v{template.version}"
                if template
                else "pipeline.prompts.personal_reading.free_weekly.v3"
            )

            # Build LLM client
            client = LLMClient()
            client.configure_slot(
                LLMSlotConfig(
                    slot=llm_config.slot,
                    provider_name=llm_config.provider_name,
                    api_endpoint=llm_config.api_endpoint,
                    model_id=llm_config.model_id,
                    api_key_encrypted=llm_config.api_key_encrypted,
                    max_tokens=llm_config.max_tokens,
                    temperature=llm_config.temperature or 0.7,
                    extra_params=llm_config.extra_params or {},
                )
            )

            # Build per-user tasks
            tasks: list[dict] = []
            for user, profile in free_users:
                try:
                    chart = profile.natal_chart_json
                    if not chart:
                        chart = calculate_natal_chart(
                            birth_date=profile.birth_date,
                            birth_time=profile.birth_time,
                            birth_latitude=profile.birth_latitude,
                            birth_longitude=profile.birth_longitude,
                            birth_timezone=profile.birth_timezone,
                            house_system=profile.house_system,
                        )
                        profile.natal_chart_json = chart
                        profile.natal_chart_computed_at = datetime.now(UTC)
                        await session.flush()

                    # Calculate transit-to-natal aspects for each day of the week
                    week_aspects: list[dict] = []
                    for day_date, day_transits in weekly_transits.items():
                        day_aspects = calculate_transit_to_natal_aspects(
                            day_transits, chart.get("positions", [])
                        )
                        for aspect in day_aspects:
                            week_aspects.append({**aspect, "date": day_date.isoformat()})

                    aggregated = _aggregate_weekly_aspects(week_aspects, limit=weekly_aspect_limit)

                    messages = build_free_reading_prompt(
                        natal_positions=chart.get("positions", []),
                        natal_angles=chart.get("angles", []),
                        current_transits=today_transits,
                        transit_to_natal=aggregated,
                        house_system=profile.house_system,
                        date_context=today,
                        week_start=week_start,
                        week_end=week_end,
                        blocked_words=blocked_words,
                        word_range=free_word_range,
                        template_text=str(template.content) if template else None,
                    )

                    tasks.append({
                        "user": user,
                        "profile": profile,
                        "messages": messages,
                    })
                except Exception:
                    logger.exception("Failed to build free reading prompt for user %s", user.id)
                    continue

            if not tasks:
                await client.close()
                logger.info("Free reading batch: 0 tasks after prep")
                return 0

            logger.info(
                "Free reading batch: generating %d readings for %s (concurrency=%d)",
                len(tasks),
                week_key,
                _BATCH_CONCURRENCY,
            )

            # ---- Phase 2: Generate (concurrent, LLM-bound) ----
            semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)

            async def _generate_one(task: dict) -> tuple[dict, float, dict]:
                async with semaphore:
                    start = time.monotonic()
                    content = await generate_with_validation(
                        client, "personal_free", task["messages"], _validate_reading_json
                    )
                    content, fix_meta = await fix_non_latin_content(content, client, "personal_free")
                    elapsed = time.monotonic() - start
                    return content, elapsed, fix_meta

            results = await asyncio.gather(
                *[_generate_one(t) for t in tasks],
                return_exceptions=True,
            )
            await client.close()

            # ---- Phase 3: Save (sequential, DB-bound) ----
            for task, result in zip(tasks, results):
                user = task["user"]
                profile = task["profile"]

                if isinstance(result, BaseException):
                    logger.exception(
                        "Failed to generate free reading for user %s: %s",
                        user.id,
                        result,
                    )
                    error_count += 1
                    continue

                content, elapsed, fix_meta = result
                elapsed_times.append(elapsed)
                if fix_meta.get("applied"):
                    non_latin_fix_count += 1

                reading = PersonalReading(
                    user_id=user.id,
                    tier="free",
                    date_context=today,
                    week_key=week_key,
                    content=content,
                    house_system_used=profile.house_system,
                    llm_slot_used="personal_free",
                    generation_metadata={
                        "elapsed_seconds": round(elapsed, 2),
                        "template_version": template_version_str,
                        "template": template_usage(template) if template else None,
                        "banned_phrase_count": len(blocked_words),
                        "coverage": {
                            "start": week_start.isoformat(),
                            "end": week_end.isoformat(),
                        },
                        "batch": True,
                        "non_latin_fix": fix_meta,
                    },
                )
                session.add(reading)
                try:
                    await session.flush()
                    gen_count += 1
                    logger.info(
                        "Generated free reading for user %s (%.1fs)", user.id, elapsed
                    )
                except IntegrityError:
                    await session.rollback()
                    skipped_count += 1
                    logger.info(
                        "Free reading for user %s week %s already exists (concurrent insert); skipping",
                        user.id,
                        week_key,
                    )

        # -- Mark BatchRun completed --
        if batch_run_id:
            try:
                total_elapsed = (datetime.now(UTC) - batch_started).total_seconds()
                async with get_session() as br_session:
                    result = await br_session.execute(
                        select(BatchRun).where(BatchRun.id == batch_run_id)
                    )
                    br = result.scalars().first()
                    if br:
                        br.status = "completed"
                        br.ended_at = datetime.now(UTC)
                        br.eligible_count = eligible_count
                        br.skipped_count = skipped_count
                        br.generated_count = gen_count
                        br.error_count = error_count
                        br.non_latin_fix_count = non_latin_fix_count
                        br.summary_json = {
                            "avg_elapsed_seconds": (
                                round(sum(elapsed_times) / len(elapsed_times), 2)
                                if elapsed_times else 0
                            ),
                            "total_elapsed_seconds": round(total_elapsed, 2),
                            "concurrency": _BATCH_CONCURRENCY,
                            "template_version": template_version_str,
                        }
            except Exception:
                logger.warning("Could not update BatchRun to completed", exc_info=True)

    except Exception as exc:
        # -- Mark BatchRun failed --
        if batch_run_id:
            try:
                async with get_session() as br_session:
                    result = await br_session.execute(
                        select(BatchRun).where(BatchRun.id == batch_run_id)
                    )
                    br = result.scalars().first()
                    if br:
                        br.status = "failed"
                        br.ended_at = datetime.now(UTC)
                        br.eligible_count = eligible_count
                        br.skipped_count = skipped_count
                        br.generated_count = gen_count
                        br.error_count = error_count
                        br.non_latin_fix_count = non_latin_fix_count
                        br.error_detail = str(exc)[:2000]
            except Exception:
                logger.warning("Could not update BatchRun to failed", exc_info=True)
        raise

    logger.info("Free reading batch complete: %d readings generated for %s", gen_count, week_key)
    return gen_count
