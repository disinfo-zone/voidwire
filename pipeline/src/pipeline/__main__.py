"""Pipeline entry point for running as a module: python -m pipeline."""

from __future__ import annotations

import asyncio
import logging
import sys

from pipeline.orchestrator import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("pipeline")


async def main() -> None:
    """Run the daily pipeline."""
    logger.info("Starting Voidwire pipeline")
    try:
        run_id = await run_pipeline()
        logger.info("Pipeline completed successfully. Run ID: %s", run_id)
    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
