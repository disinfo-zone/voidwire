"""Personal reading batch generation stage for pro subscribers."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, date, datetime

from ephemeris.natal import calculate_natal_chart, calculate_transit_to_natal_aspects
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import (
    BatchRun,
    LLMConfig,
    PersonalReading,
    PipelineRun,
    Reading,
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

from ephemeris import calculate_day
from pipeline.prompts.personal_reading import (
    PERSONAL_READING_PRO_TEMPLATE_PREFIX,
    build_pro_reading_prompt,
    resolve_personal_template_candidates,
)

logger = logging.getLogger(__name__)

_BATCH_CONCURRENCY = 50


def _validate_reading_json(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    if "title" not in data or "body" not in data:
        raise ValueError("Missing required fields: title, body")


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


async def run_personal_reading_stage(
    target_date: date,
    session: AsyncSession,
) -> int:
    """Generate personalized daily readings for all active pro subscribers.

    Uses concurrent LLM calls for throughput. Returns the number of readings generated.
    """
    # Check if personal_pro slot is configured
    result = await session.execute(
        select(LLMConfig).where(LLMConfig.slot == "personal_pro", LLMConfig.is_active)
    )
    llm_config = result.scalars().first()
    if not llm_config:
        logger.info("personal_pro LLM slot not configured, skipping personal reading stage")
        return 0

    # -- Create BatchRun record --
    batch_started = datetime.now(UTC)
    batch_run = BatchRun(
        batch_type="pro_reading",
        started_at=batch_started,
        status="running",
        target_date=target_date,
    )
    session.add(batch_run)
    await session.flush()

    eligible_count = 0
    skipped_count = 0
    gen_count = 0
    error_count = 0
    non_latin_fix_count = 0
    elapsed_times: list[float] = []
    template_version_str = ""

    try:
        # Find active pro subscribers with profiles
        result = await session.execute(
            select(User, UserProfile)
            .join(Subscription, Subscription.user_id == User.id)
            .join(UserProfile, UserProfile.user_id == User.id)
            .where(
                User.is_active,
                Subscription.status.in_(("active", "trialing")),
            )
        )
        user_profile_pairs: list[tuple[User, UserProfile]] = list(result.all())
        deduped_pairs: dict[object, tuple[User, UserProfile]] = {}
        for user, profile in user_profile_pairs:
            deduped_pairs.setdefault(user.id, (user, profile))
        pro_users = list(deduped_pairs.values())

        if not pro_users:
            logger.info("No active pro subscribers with profiles, skipping")
            batch_run.status = "completed"
            batch_run.ended_at = datetime.now(UTC)
            await session.flush()
            return 0

        eligible_count = len(pro_users)

        existing_for_day_result = await session.execute(
            select(PersonalReading.user_id).where(
                PersonalReading.tier == "pro",
                PersonalReading.date_context == target_date,
            )
        )
        existing_user_ids = set(existing_for_day_result.scalars().all())

        # Get ephemeris data
        run_result = await session.execute(
            select(PipelineRun)
            .where(PipelineRun.date_context == target_date, PipelineRun.status == "completed")
            .order_by(PipelineRun.run_number.desc())
            .limit(1)
        )
        pipeline_run = run_result.scalars().first()
        transit_positions: dict[str, dict] = {}
        if pipeline_run and pipeline_run.ephemeris_json:
            transit_positions = _normalize_transit_positions(pipeline_run.ephemeris_json.get("positions", {}))
        if not transit_positions:
            generated = await calculate_day(target_date, db_session=session)
            transit_positions = _normalize_transit_positions(generated.positions)

        # Get today's published reading for context
        reading_result = await session.execute(
            select(Reading)
            .where(Reading.date_context == target_date, Reading.status == "published")
            .order_by(Reading.published_at.desc())
            .limit(1)
        )
        daily_reading = reading_result.scalars().first()
        daily_ctx = None
        if daily_reading:
            content = daily_reading.published_standard or daily_reading.generated_standard or {}
            daily_ctx = {"title": content.get("title", ""), "body": content.get("body", "")}

        pipeline_settings = await load_pipeline_settings(session)
        personal_settings = pipeline_settings.personal
        if not bool(personal_settings.enabled):
            logger.info("personal readings disabled via pipeline settings; skipping")
            batch_run.status = "completed"
            batch_run.ended_at = datetime.now(UTC)
            await session.flush()
            return 0

        blocked_words = [
            str(phrase).strip()
            for phrase in (pipeline_settings.synthesis.banned_phrases or [])
            if str(phrase).strip()
        ]
        pro_word_range = personal_settings.pro_word_range
        pro_candidates = resolve_personal_template_candidates(
            "pro",
            personal_settings.pro_template_name,
        )
        pro_template = await load_active_prompt_template(
            session,
            candidates=pro_candidates,
            prefix=PERSONAL_READING_PRO_TEMPLATE_PREFIX,
        )
        template_version_str = (
            f"{pro_template.template_name}.v{pro_template.version}"
            if pro_template
            else "pipeline.prompts.personal_reading.pro_daily.v3"
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

        # --- Phase 1: Build prompts for all users (sequential, DB-dependent) ---
        tasks: list[dict] = []
        for user, profile in pro_users:
            if user.id in existing_user_ids:
                skipped_count += 1
                continue

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

                transit_natal = calculate_transit_to_natal_aspects(
                    transit_positions, chart.get("positions", [])
                )

                messages = build_pro_reading_prompt(
                    natal_positions=chart.get("positions", []),
                    natal_angles=chart.get("angles", []),
                    current_transits=transit_positions,
                    transit_to_natal=transit_natal,
                    house_system=profile.house_system,
                    date_context=target_date,
                    daily_reading_context=daily_ctx,
                    blocked_words=blocked_words,
                    word_range=pro_word_range,
                    template_text=str(pro_template.content) if pro_template else None,
                )

                tasks.append({
                    "user": user,
                    "profile": profile,
                    "messages": messages,
                })
            except Exception:
                logger.exception("Failed to build prompt for user %s", user.id)
                continue

        if not tasks:
            await client.close()
            logger.info("Personal reading stage complete: 0 readings to generate")
            batch_run.status = "completed"
            batch_run.ended_at = datetime.now(UTC)
            batch_run.eligible_count = eligible_count
            batch_run.skipped_count = skipped_count
            await session.flush()
            return 0

        logger.info(
            "Personal reading stage: generating %d readings with concurrency=%d",
            len(tasks),
            _BATCH_CONCURRENCY,
        )

        # --- Phase 2: Fire LLM calls concurrently ---
        semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)

        async def _generate_one(task: dict) -> tuple[dict, float, dict]:
            async with semaphore:
                start = time.monotonic()
                reading_content = await generate_with_validation(
                    client, "personal_pro", task["messages"], _validate_reading_json
                )
                reading_content, fix_meta = await fix_non_latin_content(reading_content, client, "personal_pro")
                elapsed = time.monotonic() - start
                return reading_content, elapsed, fix_meta

        results = await asyncio.gather(
            *[_generate_one(t) for t in tasks],
            return_exceptions=True,
        )
        await client.close()

        # --- Phase 3: Save results to DB (sequential) ---
        template = pro_template
        for task, result in zip(tasks, results):
            user = task["user"]
            profile = task["profile"]

            if isinstance(result, BaseException):
                logger.exception(
                    "Failed to generate pro reading for user %s: %s", user.id, result
                )
                error_count += 1
                continue

            reading_content, elapsed, fix_meta = result
            elapsed_times.append(elapsed)
            if fix_meta.get("applied"):
                non_latin_fix_count += 1

            reading = PersonalReading(
                user_id=user.id,
                tier="pro",
                date_context=target_date,
                content=reading_content,
                house_system_used=profile.house_system,
                llm_slot_used="personal_pro",
                generation_metadata={
                    "elapsed_seconds": round(elapsed, 2),
                    "template_version": template_version_str,
                    "template": template_usage(template) if template else None,
                    "banned_phrase_count": len(blocked_words),
                    "non_latin_fix": fix_meta,
                },
            )
            session.add(reading)
            await session.flush()
            gen_count += 1
            existing_user_ids.add(user.id)
            logger.info("Generated pro reading for user %s (%.1fs)", user.id, elapsed)

        # -- Mark BatchRun completed --
        total_elapsed = (datetime.now(UTC) - batch_started).total_seconds()
        batch_run.status = "completed"
        batch_run.ended_at = datetime.now(UTC)
        batch_run.eligible_count = eligible_count
        batch_run.skipped_count = skipped_count
        batch_run.generated_count = gen_count
        batch_run.error_count = error_count
        batch_run.non_latin_fix_count = non_latin_fix_count
        batch_run.summary_json = {
            "avg_elapsed_seconds": (
                round(sum(elapsed_times) / len(elapsed_times), 2)
                if elapsed_times else 0
            ),
            "total_elapsed_seconds": round(total_elapsed, 2),
            "concurrency": _BATCH_CONCURRENCY,
            "template_version": template_version_str,
        }
        await session.flush()

    except Exception as exc:
        batch_run.status = "failed"
        batch_run.ended_at = datetime.now(UTC)
        batch_run.eligible_count = eligible_count
        batch_run.skipped_count = skipped_count
        batch_run.generated_count = gen_count
        batch_run.error_count = error_count
        batch_run.non_latin_fix_count = non_latin_fix_count
        batch_run.error_detail = str(exc)[:2000]
        await session.flush()
        raise

    logger.info("Personal reading stage complete: %d readings generated", gen_count)
    return gen_count
