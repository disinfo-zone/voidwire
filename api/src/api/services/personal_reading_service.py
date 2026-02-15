"""Personal reading generation and caching service."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, date, datetime

from ephemeris.natal import calculate_natal_chart, calculate_transit_to_natal_aspects
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import PersonalReading, PipelineRun, Reading, User
from voidwire.services.llm_client import LLMClient, LLMSlotConfig, generate_with_validation

logger = logging.getLogger(__name__)


def _current_week_key(d: date) -> str:
    """Return ISO week key like '2026-W07'."""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _validate_reading_json(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    if "title" not in data or "body" not in data:
        raise ValueError("Missing required fields: title, body")


async def _get_today_ephemeris(db: AsyncSession, target: date) -> dict | None:
    """Fetch today's ephemeris data from the most recent pipeline run."""
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.date_context == target, PipelineRun.status == "completed")
        .order_by(PipelineRun.run_number.desc())
        .limit(1)
    )
    run = result.scalars().first()
    if run and run.ephemeris_json:
        return run.ephemeris_json
    return None


async def _get_today_reading_context(db: AsyncSession, target: date) -> dict | None:
    """Fetch today's published reading for pro-tier context injection."""
    result = await db.execute(
        select(Reading)
        .where(Reading.date_context == target, Reading.status == "published")
        .order_by(Reading.published_at.desc())
        .limit(1)
    )
    reading = result.scalars().first()
    if reading:
        content = reading.published_standard or reading.generated_standard or {}
        return {"title": content.get("title", ""), "body": content.get("body", "")}
    return None


async def _build_llm_client(db: AsyncSession, slot_name: str) -> LLMClient | None:
    """Build an LLM client configured for the given slot."""
    from voidwire.models import LLMConfig

    result = await db.execute(
        select(LLMConfig).where(LLMConfig.slot == slot_name, LLMConfig.is_active)
    )
    config = result.scalars().first()
    if not config:
        logger.warning("LLM slot '%s' not configured or inactive", slot_name)
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


class PersonalReadingService:
    """Service for generating and retrieving personalized readings."""

    @staticmethod
    async def get_or_generate_free_reading(
        user: User,
        db: AsyncSession,
        redis=None,
    ) -> PersonalReading | None:
        """Get or generate a free weekly personal reading."""
        profile = user.profile
        if not profile:
            return None

        today = date.today()
        week_key = _current_week_key(today)

        # Check Redis cache
        if redis:
            try:
                cache_key = f"personal_reading:free:{user.id}:{week_key}"
                cached = await redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Return a transient object for display
                    return PersonalReading(
                        user_id=user.id,
                        tier="free",
                        date_context=today,
                        week_key=week_key,
                        content=data,
                        house_system_used=profile.house_system,
                        llm_slot_used="personal_free",
                    )
            except Exception as e:
                logger.warning("Redis cache read failed: %s", e)

        # Check DB
        result = await db.execute(
            select(PersonalReading).where(
                PersonalReading.user_id == user.id,
                PersonalReading.tier == "free",
                PersonalReading.week_key == week_key,
            )
        )
        existing = result.scalars().first()
        if existing:
            return existing

        # Generate new reading
        reading = await PersonalReadingService._generate_reading(
            user, profile, db, "free", today, week_key=week_key
        )
        if not reading:
            return None

        # Cache in Redis
        if redis:
            try:
                cache_key = f"personal_reading:free:{user.id}:{week_key}"
                # TTL: seconds until end of ISO week (Sunday 23:59:59)
                days_left = 7 - today.isoweekday()
                ttl = max(3600, days_left * 86400)
                await redis.set(cache_key, json.dumps(reading.content), ex=ttl)
            except Exception as e:
                logger.warning("Redis cache write failed: %s", e)

        return reading

    @staticmethod
    async def get_or_generate_pro_reading(
        user: User,
        db: AsyncSession,
    ) -> PersonalReading | None:
        """Get or generate a pro daily personal reading."""
        profile = user.profile
        if not profile:
            return None

        today = date.today()

        # Check DB for today's reading
        result = await db.execute(
            select(PersonalReading).where(
                PersonalReading.user_id == user.id,
                PersonalReading.tier == "pro",
                PersonalReading.date_context == today,
            )
        )
        existing = result.scalars().first()
        if existing:
            return existing

        # Generate on-demand (batch may not have run yet)
        return await PersonalReadingService._generate_reading(user, profile, db, "pro", today)

    @staticmethod
    async def _generate_reading(
        user: User,
        profile,
        db: AsyncSession,
        tier: str,
        target_date: date,
        week_key: str | None = None,
    ) -> PersonalReading | None:
        """Generate a personalized reading using the appropriate LLM slot."""
        slot_name = f"personal_{tier}"
        client = await _build_llm_client(db, slot_name)
        if not client:
            return None

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
                # Cache computed chart to avoid repeated heavy computations.
                profile.natal_chart_json = chart
                profile.natal_chart_computed_at = datetime.now(UTC)
                await db.flush()

            # Get current transit data
            ephemeris = await _get_today_ephemeris(db, target_date)
            transit_positions_raw = ephemeris.get("positions", {}) if ephemeris else {}
            transit_positions = (
                transit_positions_raw if isinstance(transit_positions_raw, dict) else {}
            )

            # Calculate transit-to-natal aspects
            transit_natal = calculate_transit_to_natal_aspects(
                transit_positions, chart.get("positions", [])
            )

            # Build prompt
            from pipeline.prompts.personal_reading import (
                build_free_reading_prompt,
                build_pro_reading_prompt,
            )

            if tier == "free":
                messages = build_free_reading_prompt(
                    natal_positions=chart.get("positions", []),
                    natal_angles=chart.get("angles", []),
                    current_transits=transit_positions,
                    transit_to_natal=transit_natal,
                    house_system=profile.house_system,
                    date_context=target_date,
                )
            else:
                daily_ctx = await _get_today_reading_context(db, target_date)
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
                client, slot_name, messages, _validate_reading_json
            )
            elapsed = time.monotonic() - start

            reading = PersonalReading(
                user_id=user.id,
                tier=tier,
                date_context=target_date,
                week_key=week_key or (_current_week_key(target_date) if tier == "free" else None),
                content=content,
                house_system_used=profile.house_system,
                llm_slot_used=slot_name,
                generation_metadata={"elapsed_seconds": round(elapsed, 2)},
            )
            db.add(reading)
            try:
                await db.flush()
            except IntegrityError:
                # Another worker/request may have inserted this row concurrently.
                await db.rollback()
                result = await db.execute(
                    select(PersonalReading).where(
                        PersonalReading.user_id == user.id,
                        PersonalReading.tier == tier,
                        PersonalReading.date_context == target_date,
                    )
                )
                return result.scalars().first()
            return reading

        except Exception:
            logger.exception("Failed to generate %s personal reading for user %s", tier, user.id)
            return None
        finally:
            await client.close()
