"""Pipeline entry point for running as a module: python -m pipeline."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from voidwire.config import get_settings
from voidwire.database import get_session
from voidwire.models import PipelineRun, SiteSetting

from pipeline.orchestrator import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("pipeline")

SCHEDULE_SETTING_KEY = "pipeline.schedule"
TIMEZONE_SETTING_KEY = "pipeline.timezone"
RUN_ON_START_SETTING_KEY = "pipeline.run_on_start"


def _parse_daily_schedule(schedule: str) -> tuple[int, int]:
    """Parse a simple daily cron expression: M H * * *."""
    parts = schedule.split()
    if len(parts) != 5:
        raise ValueError(f"Unsupported schedule '{schedule}'. Expected 'M H * * *'.")
    minute_str, hour_str, dom, month, dow = parts
    if dom != "*" or month != "*" or dow != "*":
        raise ValueError(f"Unsupported schedule '{schedule}'. Only daily schedules are supported.")

    minute = int(minute_str)
    hour = int(hour_str)
    if minute < 0 or minute > 59 or hour < 0 or hour > 23:
        raise ValueError(f"Invalid schedule '{schedule}'.")
    return hour, minute


def _next_run(now: datetime, hour: int, minute: int) -> datetime:
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


async def _run_once(*, fail_hard: bool) -> None:
    try:
        run_id = await run_pipeline()
        logger.info("Pipeline completed successfully. Run ID: %s", run_id)
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc)
        if fail_hard:
            raise


async def _mark_orphaned_running_runs() -> None:
    """Convert stale 'running' rows to failed on process startup."""
    try:
        async with get_session() as session:
            result = await session.execute(
                select(PipelineRun).where(PipelineRun.status == "running")
            )
            orphaned = result.scalars().all()
            if not orphaned:
                return

            now = datetime.now(UTC)
            for run in orphaned:
                run.status = "failed"
                run.ended_at = now
                if not run.error_detail:
                    run.error_detail = (
                        "Run marked failed after pipeline process restart before completion."
                    )
            logger.warning("Marked %d orphaned running run(s) as failed", len(orphaned))
    except Exception as exc:
        logger.warning("Could not mark orphaned runs on startup: %s", exc)


async def _load_scheduler_config() -> tuple[str, str, bool]:
    """Return effective scheduler config (DB override -> env default)."""
    settings = get_settings()
    schedule = settings.pipeline_schedule
    timezone_name = settings.timezone
    run_on_start = settings.pipeline_run_on_start

    try:
        async with get_session() as session:
            result = await session.execute(
                select(SiteSetting).where(
                    SiteSetting.key.in_(
                        [SCHEDULE_SETTING_KEY, TIMEZONE_SETTING_KEY, RUN_ON_START_SETTING_KEY]
                    )
                )
            )
            by_key = {row.key: row for row in result.scalars().all()}

            schedule_setting = by_key.get(SCHEDULE_SETTING_KEY)
            if schedule_setting and isinstance(schedule_setting.value, dict):
                override = str(schedule_setting.value.get("cron", "")).strip()
                if override:
                    schedule = override

            timezone_setting = by_key.get(TIMEZONE_SETTING_KEY)
            if timezone_setting and isinstance(timezone_setting.value, dict):
                override = str(timezone_setting.value.get("value", "")).strip()
                if override:
                    timezone_name = override

            run_on_start_setting = by_key.get(RUN_ON_START_SETTING_KEY)
            if run_on_start_setting and isinstance(run_on_start_setting.value, dict):
                run_on_start = bool(run_on_start_setting.value.get("enabled", run_on_start))
    except Exception as exc:
        logger.warning("Could not load scheduler overrides from DB: %s", exc)

    return schedule, timezone_name, run_on_start


async def _run_scheduler() -> None:
    schedule, timezone_name, run_on_start = await _load_scheduler_config()
    if run_on_start:
        logger.info("Running pipeline immediately on startup")
        await _run_once(fail_hard=False)

    last_announced: tuple[str, str, str] | None = None
    while True:
        schedule, timezone_name, _ = await _load_scheduler_config()

        try:
            hour, minute = _parse_daily_schedule(schedule)
            tz = ZoneInfo(timezone_name)
        except Exception as exc:
            logger.error(
                "Invalid scheduler configuration schedule='%s' timezone='%s': %s",
                schedule,
                timezone_name,
                exc,
            )
            await asyncio.sleep(30)
            continue

        now = datetime.now(tz)
        target = _next_run(now, hour, minute)
        signature = (schedule, timezone_name, target.isoformat())
        if signature != last_announced:
            sleep_seconds = max((target - now).total_seconds(), 1.0)
            logger.info(
                "Next pipeline run scheduled for %s (%s seconds) using '%s' %s",
                target.isoformat(),
                int(sleep_seconds),
                schedule,
                timezone_name,
            )
            last_announced = signature

        sleep_seconds = max((target - now).total_seconds(), 1.0)
        if sleep_seconds > 30:
            await asyncio.sleep(30)
            continue

        await asyncio.sleep(sleep_seconds)
        await _run_once(fail_hard=False)


async def main() -> None:
    """Run one pipeline pass or scheduler mode."""
    logger.info("Starting Voidwire pipeline")
    await _mark_orphaned_running_runs()
    if "--once" in sys.argv[1:]:
        try:
            await _run_once(fail_hard=True)
        except Exception:
            sys.exit(1)
        return

    try:
        await _run_scheduler()
    except Exception as exc:
        logger.error("Pipeline scheduler failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
