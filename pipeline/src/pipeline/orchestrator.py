"""Pipeline orchestrator - main daily pipeline runner."""
from __future__ import annotations
import hashlib
import json
import logging
import subprocess
import uuid
from datetime import date, datetime, timezone
from typing import Any
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.database import get_session
from voidwire.models import PipelineRun, Reading
from voidwire.schemas.pipeline import RegenerationMode
from pipeline.stages.ephemeris_stage import run_ephemeris_stage
from pipeline.stages.ingestion_stage import run_ingestion_stage
from pipeline.stages.distillation_stage import run_distillation_stage
from pipeline.stages.embedding_stage import run_embedding_stage
from pipeline.stages.selection_stage import run_selection_stage
from pipeline.stages.thread_stage import run_thread_stage
from pipeline.stages.synthesis_stage import run_synthesis_stage
from pipeline.stages.publish_stage import run_publish_stage

logger = logging.getLogger(__name__)
SILENCE_READING = {"title": "The Signal Obscured", "body": "The signal is obscured. The planetary mechanism grinds on, silent and unobserved.", "word_count": 14}

def _get_code_version() -> str:
    try:
        r = subprocess.run(["git","rev-parse","--short","HEAD"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"

def _content_hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

def _generate_seed(date_context: date, run_id: uuid.UUID) -> int:
    return int(hashlib.sha256(f"{date_context.isoformat()}{run_id}".encode()).hexdigest()[:16], 16)

async def run_pipeline(date_context: date | None = None, regeneration_mode: RegenerationMode | None = None, parent_run_id: uuid.UUID | None = None) -> uuid.UUID:
    settings = get_settings()
    if date_context is None:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(settings.timezone)
        date_context = datetime.now(tz).date()
    run_id = uuid.uuid4()
    seed = _generate_seed(date_context, run_id)
    async with get_session() as session:
        lock_key = int(hashlib.sha256(date_context.isoformat().encode()).hexdigest()[:15], 16) % (2**31)
        result = await session.execute(sa_text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key})
        if not result.scalar():
            raise RuntimeError(f"Could not acquire advisory lock for {date_context}")
        try:
            existing = await session.execute(sa_text("SELECT COALESCE(MAX(run_number), 0) FROM pipeline_runs WHERE date_context = :dc"), {"dc": date_context})
            run_number = existing.scalar() + 1
            run = PipelineRun(id=run_id, date_context=date_context, run_number=run_number, started_at=datetime.now(timezone.utc), status="running", code_version=_get_code_version(), seed=seed, template_versions={}, model_config_json={}, regeneration_mode=regeneration_mode.value if regeneration_mode else None, parent_run_id=parent_run_id, ephemeris_json={}, distilled_signals={}, selected_signals={}, thread_snapshot={}, prompt_payloads={}, ephemeris_hash="", distillation_hash="", selection_hash="")
            session.add(run)
            await session.flush()
            ephemeris_data = await run_ephemeris_stage(date_context, session)
            run.ephemeris_json = ephemeris_data
            run.ephemeris_hash = _content_hash(ephemeris_data)
            sky_only = False
            try:
                raw_articles = await run_ingestion_stage(date_context, session)
                if not raw_articles:
                    sky_only = True
                    distilled = []
                else:
                    distilled = await run_distillation_stage(raw_articles, run_id, date_context, session)
            except Exception as e:
                logger.error("Ingestion failed: %s", e)
                sky_only = True
                distilled = []
            run.distilled_signals = distilled if isinstance(distilled, list) else []
            run.distillation_hash = _content_hash(distilled)
            if distilled and not sky_only:
                try:
                    distilled = await run_embedding_stage(distilled, session)
                except Exception as e:
                    logger.warning("Embedding failed: %s", e)
            selected = await run_selection_stage(distilled, seed) if distilled and not sky_only else []
            run.selected_signals = selected if isinstance(selected, list) else []
            run.selection_hash = _content_hash({"selected": selected, "seed": seed})
            try:
                thread_snapshot = await run_thread_stage(distilled, date_context, session)
            except Exception as e:
                logger.warning("Thread tracking failed: %s", e)
                thread_snapshot = []
            run.thread_snapshot = thread_snapshot
            try:
                synthesis_result = await run_synthesis_stage(ephemeris_data, selected, thread_snapshot, date_context, sky_only, session)
                run.interpretive_plan = synthesis_result.get("interpretive_plan")
                run.generated_output = synthesis_result.get("generated_output")
                run.prompt_payloads = synthesis_result.get("prompt_payloads", {})
                reading = Reading(run_id=run_id, date_context=date_context, status="pending", generated_standard=synthesis_result.get("standard_reading", SILENCE_READING), generated_extended=synthesis_result.get("extended_reading", {"title":"","subtitle":"","sections":[],"word_count":0}), generated_annotations=synthesis_result.get("annotations", []))
                session.add(reading)
            except Exception as e:
                logger.error("Synthesis failed: %s", e)
                reading = Reading(run_id=run_id, date_context=date_context, status="pending", generated_standard=SILENCE_READING, generated_extended={"title":"","subtitle":"","sections":[],"word_count":0}, generated_annotations=[])
                session.add(reading)
                run.error_detail = str(e)
            await run_publish_stage(reading, session)
            run.status = "completed"
            run.ended_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.exception("Pipeline failed: %s", e)
            run.status = "failed"
            run.error_detail = str(e)
            run.ended_at = datetime.now(timezone.utc)
            raise
        finally:
            await session.execute(sa_text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
    return run_id
