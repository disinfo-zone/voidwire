"""Personal reading batch generation stage for pro subscribers."""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime

from ephemeris.natal import calculate_natal_chart, calculate_transit_to_natal_aspects
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import (
    LLMConfig,
    PersonalReading,
    PipelineRun,
    Reading,
    Subscription,
    User,
    UserProfile,
)
from voidwire.services.llm_client import LLMClient, LLMSlotConfig, generate_with_validation

from pipeline.prompts.personal_reading import build_pro_reading_prompt

logger = logging.getLogger(__name__)


def _validate_reading_json(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    if "title" not in data or "body" not in data:
        raise ValueError("Missing required fields: title, body")


async def run_personal_reading_stage(
    target_date: date,
    session: AsyncSession,
) -> int:
    """Generate personalized daily readings for all active pro subscribers.

    Returns the number of readings generated.
    """
    # Check if personal_pro slot is configured
    result = await session.execute(
        select(LLMConfig).where(LLMConfig.slot == "personal_pro", LLMConfig.is_active)
    )
    llm_config = result.scalars().first()
    if not llm_config:
        logger.info("personal_pro LLM slot not configured, skipping personal reading stage")
        return 0

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
        return 0

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
        transit_positions_raw = pipeline_run.ephemeris_json.get("positions", {})
        if isinstance(transit_positions_raw, dict):
            transit_positions = transit_positions_raw

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

    generated = 0
    try:
        for user, profile in pro_users:
            # Skip if already generated
            if user.id in existing_user_ids:
                continue

            try:
                # Compute natal chart
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
                )

                start = time.monotonic()
                content = await generate_with_validation(
                    client, "personal_pro", messages, _validate_reading_json
                )
                elapsed = time.monotonic() - start

                reading = PersonalReading(
                    user_id=user.id,
                    tier="pro",
                    date_context=target_date,
                    content=content,
                    house_system_used=profile.house_system,
                    llm_slot_used="personal_pro",
                    generation_metadata={"elapsed_seconds": round(elapsed, 2)},
                )
                session.add(reading)
                await session.flush()
                generated += 1
                existing_user_ids.add(user.id)
                logger.info("Generated pro reading for user %s", user.id)

            except Exception:
                logger.exception("Failed to generate pro reading for user %s", user.id)
                continue
    finally:
        await client.close()

    logger.info("Personal reading stage complete: %d readings generated", generated)
    return generated
