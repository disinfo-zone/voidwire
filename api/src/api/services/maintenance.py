"""Background maintenance loop (billing reconciliation + retention cleanup)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from voidwire.config import get_settings
from voidwire.database import get_session

from api.services.billing_reconciliation import run_billing_reconciliation
from api.services.governance import run_retention_cleanup

logger = logging.getLogger(__name__)


async def run_maintenance_worker(
    stop_event: asyncio.Event,
    *,
    poll_interval_seconds: float = 300.0,
) -> None:
    settings = get_settings()
    reconcile_interval = timedelta(
        hours=max(1, int(settings.billing_reconciliation_interval_hours))
    )
    retention_interval = timedelta(hours=24)
    last_reconcile_at: datetime | None = None
    last_retention_at: datetime | None = None

    logger.info("Maintenance worker started")
    try:
        while not stop_event.is_set():
            now = datetime.now(UTC)
            should_reconcile = (
                last_reconcile_at is None or (now - last_reconcile_at) >= reconcile_interval
            )
            should_retention = (
                last_retention_at is None or (now - last_retention_at) >= retention_interval
            )

            if should_reconcile:
                try:
                    async with get_session() as db:
                        await run_billing_reconciliation(db, trigger="scheduled")
                    last_reconcile_at = datetime.now(UTC)
                except Exception:
                    logger.exception("Scheduled billing reconciliation failed")

            if should_retention:
                try:
                    async with get_session() as db:
                        await run_retention_cleanup(db, trigger="scheduled")
                    last_retention_at = datetime.now(UTC)
                except Exception:
                    logger.exception("Scheduled retention cleanup failed")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_interval_seconds)
            except TimeoutError:
                pass
    finally:
        logger.info("Maintenance worker stopped")
