"""Recalculate natal charts for all user profiles."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from ephemeris.natal import calculate_natal_chart
from sqlalchemy import select
from voidwire.database import close_engine, get_session_factory
from voidwire.models import UserProfile

from api.services.birth_timezone import resolve_birth_timezone


async def recalculate_all_natal_charts(*, batch_size: int, dry_run: bool) -> dict[str, int]:
    """Recompute every profile chart, auto-correcting timezone by coordinates."""
    factory = get_session_factory()
    stats = {
        "profiles_seen": 0,
        "charts_recalculated": 0,
        "timezones_corrected": 0,
    }
    now = datetime.now(UTC)

    async with factory() as db:
        result = await db.execute(select(UserProfile).order_by(UserProfile.created_at.asc()))
        profiles = list(result.scalars().all())

        pending_writes = 0
        for profile in profiles:
            stats["profiles_seen"] += 1

            resolved_timezone, overridden = resolve_birth_timezone(
                latitude=profile.birth_latitude,
                longitude=profile.birth_longitude,
                fallback_timezone=profile.birth_timezone,
            )
            if overridden:
                profile.birth_timezone = resolved_timezone
                stats["timezones_corrected"] += 1

            chart = calculate_natal_chart(
                birth_date=profile.birth_date,
                birth_time=profile.birth_time,
                birth_latitude=profile.birth_latitude,
                birth_longitude=profile.birth_longitude,
                birth_timezone=profile.birth_timezone,
                house_system=profile.house_system,
            )
            profile.natal_chart_json = chart
            profile.natal_chart_computed_at = now
            profile.updated_at = now
            stats["charts_recalculated"] += 1
            pending_writes += 1

            if not dry_run and pending_writes >= batch_size:
                await db.commit()
                pending_writes = 0

        if dry_run:
            await db.rollback()
        elif pending_writes > 0:
            await db.commit()

    await close_engine()
    return stats


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recalculate natal charts for all profiles.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Commit after this many profile updates (default: 250).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute corrections without committing database writes.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    stats = asyncio.run(
        recalculate_all_natal_charts(batch_size=max(args.batch_size, 1), dry_run=bool(args.dry_run))
    )
    print(
        "natal-chart-recalc:",
        f"profiles_seen={stats['profiles_seen']}",
        f"charts_recalculated={stats['charts_recalculated']}",
        f"timezones_corrected={stats['timezones_corrected']}",
        "(dry-run)" if args.dry_run else "",
    )


if __name__ == "__main__":
    main()

