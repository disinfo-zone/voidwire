"""Personal reading generation and caching service."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, date, datetime, timedelta

from ephemeris.natal import calculate_natal_chart, calculate_transit_to_natal_aspects
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import PersonalReading, PipelineRun, Reading, User
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

logger = logging.getLogger(__name__)


def _current_week_key(d: date) -> str:
    """Return ISO week key like '2026-W07'."""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_bounds(target_date: date) -> tuple[date, date]:
    start = target_date - timedelta(days=target_date.weekday())
    end = start + timedelta(days=6)
    return start, end


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


async def _get_transit_positions_for_date(db: AsyncSession, target: date) -> dict[str, dict]:
    ephemeris = await _get_today_ephemeris(db, target)
    from_pipeline = _normalize_transit_positions(ephemeris.get("positions", {}) if ephemeris else {})
    if from_pipeline:
        return from_pipeline

    generated = await calculate_day(target, db_session=db)
    return _normalize_transit_positions(generated.positions)


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
        force_refresh: bool = False,
    ) -> PersonalReading | None:
        """Get or generate a free weekly personal reading."""
        profile = user.profile
        if not profile:
            return None

        today = date.today()
        week_key = _current_week_key(today)
        existing_for_week: PersonalReading | None = None

        # Check Redis cache
        if redis and not force_refresh:
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
        existing_for_week = result.scalars().first()
        if existing_for_week and not force_refresh:
            return existing_for_week

        # Generate new reading
        target_date = existing_for_week.date_context if (force_refresh and existing_for_week) else today
        reading = await PersonalReadingService._generate_reading(
            user,
            profile,
            db,
            "free",
            target_date,
            week_key=week_key,
            force_refresh=force_refresh,
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
        force_refresh: bool = False,
    ) -> PersonalReading | None:
        """Get or generate a pro daily personal reading."""
        profile = user.profile
        if not profile:
            return None

        today = date.today()

        # Check DB for today's reading
        if not force_refresh:
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
        return await PersonalReadingService._generate_reading(
            user,
            profile,
            db,
            "pro",
            today,
            force_refresh=force_refresh,
        )

    @staticmethod
    async def _generate_reading(
        user: User,
        profile,
        db: AsyncSession,
        tier: str,
        target_date: date,
        week_key: str | None = None,
        force_refresh: bool = False,
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

            today_transits = await _get_transit_positions_for_date(db, target_date)
            week_start, week_end = _week_bounds(target_date)
            if tier == "free":
                week_aspects: list[dict] = []
                day = week_start
                while day <= week_end:
                    day_transits = await _get_transit_positions_for_date(db, day)
                    day_aspects = calculate_transit_to_natal_aspects(
                        day_transits,
                        chart.get("positions", []),
                    )
                    for aspect in day_aspects:
                        week_aspects.append(
                            {
                                **aspect,
                                "date": day.isoformat(),
                            }
                        )
                    day += timedelta(days=1)
                transit_natal = _aggregate_weekly_aspects(week_aspects, limit=60)
            else:
                transit_natal = calculate_transit_to_natal_aspects(
                    today_transits,
                    chart.get("positions", []),
                )

            # Build prompt
            from pipeline.prompts.personal_reading import (
                PERSONAL_READING_FREE_TEMPLATE_PREFIX,
                PERSONAL_READING_PRO_TEMPLATE_PREFIX,
                build_free_reading_prompt,
                build_pro_reading_prompt,
                resolve_personal_template_candidates,
            )

            pipeline_settings = await load_pipeline_settings(db)
            personal_settings = pipeline_settings.personal
            if not bool(personal_settings.enabled):
                logger.info("Personal reading generation disabled by pipeline settings")
                return None

            banned_phrases = [
                str(phrase).strip()
                for phrase in (pipeline_settings.synthesis.banned_phrases or [])
                if str(phrase).strip()
            ]
            free_word_range = _normalize_word_range(
                personal_settings.free_word_range,
                (300, 500),
            )
            pro_word_range = _normalize_word_range(
                personal_settings.pro_word_range,
                (600, 1000),
            )
            weekly_aspect_limit = max(5, min(60, int(personal_settings.weekly_aspect_limit or 20)))

            template = None
            template_version = ""
            if tier == "free":
                free_candidates = resolve_personal_template_candidates(
                    "free",
                    personal_settings.free_template_name,
                )
                template = await load_active_prompt_template(
                    db,
                    candidates=free_candidates,
                    prefix=PERSONAL_READING_FREE_TEMPLATE_PREFIX,
                )
                transit_natal = _aggregate_weekly_aspects(transit_natal, limit=weekly_aspect_limit)
                messages = build_free_reading_prompt(
                    natal_positions=chart.get("positions", []),
                    natal_angles=chart.get("angles", []),
                    current_transits=today_transits,
                    transit_to_natal=transit_natal,
                    house_system=profile.house_system,
                    date_context=target_date,
                    week_start=week_start,
                    week_end=week_end,
                    blocked_words=banned_phrases,
                    word_range=free_word_range,
                    template_text=str(template.content) if template else None,
                )
                template_version = (
                    f"{template.template_name}.v{template.version}"
                    if template
                    else "pipeline.prompts.personal_reading.free_weekly.v3"
                )
            else:
                pro_candidates = resolve_personal_template_candidates(
                    "pro",
                    personal_settings.pro_template_name,
                )
                template = await load_active_prompt_template(
                    db,
                    candidates=pro_candidates,
                    prefix=PERSONAL_READING_PRO_TEMPLATE_PREFIX,
                )
                daily_ctx = await _get_today_reading_context(db, target_date)
                messages = build_pro_reading_prompt(
                    natal_positions=chart.get("positions", []),
                    natal_angles=chart.get("angles", []),
                    current_transits=today_transits,
                    transit_to_natal=transit_natal,
                    house_system=profile.house_system,
                    date_context=target_date,
                    daily_reading_context=daily_ctx,
                    blocked_words=banned_phrases,
                    word_range=pro_word_range,
                    template_text=str(template.content) if template else None,
                )
                template_version = (
                    f"{template.template_name}.v{template.version}"
                    if template
                    else "pipeline.prompts.personal_reading.pro_daily.v3"
                )

            start = time.monotonic()
            content = await generate_with_validation(
                client, slot_name, messages, _validate_reading_json
            )
            content, fix_meta = await fix_non_latin_content(content, client, slot_name)
            elapsed = time.monotonic() - start
            metadata = {
                "elapsed_seconds": round(elapsed, 2),
                "template_version": template_version,
                "template": template_usage(template) if template else None,
                "banned_phrase_count": len(banned_phrases),
                "coverage": {
                    "start": week_start.isoformat() if tier == "free" else target_date.isoformat(),
                    "end": week_end.isoformat() if tier == "free" else target_date.isoformat(),
                },
                "non_latin_fix": fix_meta,
            }

            if force_refresh:
                if tier == "free":
                    refresh_result = await db.execute(
                        select(PersonalReading)
                        .where(
                            PersonalReading.user_id == user.id,
                            PersonalReading.tier == "free",
                            PersonalReading.week_key == (week_key or _current_week_key(target_date)),
                        )
                        .order_by(PersonalReading.created_at.desc())
                        .limit(1)
                    )
                else:
                    refresh_result = await db.execute(
                        select(PersonalReading)
                        .where(
                            PersonalReading.user_id == user.id,
                            PersonalReading.tier == tier,
                            PersonalReading.date_context == target_date,
                        )
                        .order_by(PersonalReading.created_at.desc())
                        .limit(1)
                    )
                existing_refresh = refresh_result.scalars().first()
                if existing_refresh:
                    existing_refresh.content = content
                    existing_refresh.week_key = (
                        week_key or _current_week_key(target_date)
                        if tier == "free"
                        else existing_refresh.week_key
                    )
                    existing_refresh.house_system_used = profile.house_system
                    existing_refresh.llm_slot_used = slot_name
                    existing_refresh.generation_metadata = metadata
                    await db.flush()
                    return existing_refresh

            reading = PersonalReading(
                user_id=user.id,
                tier=tier,
                date_context=target_date,
                week_key=week_key or (_current_week_key(target_date) if tier == "free" else None),
                content=content,
                house_system_used=profile.house_system,
                llm_slot_used=slot_name,
                generation_metadata=metadata,
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
