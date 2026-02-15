"""Pipeline orchestrator - main daily pipeline runner."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import uuid
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.database import get_engine, get_session
from voidwire.models import AstronomicalEvent, PipelineRun, Reading
from voidwire.schemas.pipeline import RegenerationMode
from voidwire.services.pipeline_settings import load_pipeline_settings

from pipeline.stages.distillation_stage import run_distillation_stage
from pipeline.stages.embedding_stage import run_embedding_stage
from pipeline.stages.ephemeris_stage import run_ephemeris_stage
from pipeline.stages.ingestion_stage import run_ingestion_stage
from pipeline.stages.publish_stage import run_publish_stage
from pipeline.stages.selection_stage import run_selection_stage
from pipeline.stages.synthesis_stage import SILENCE_READING, run_synthesis_stage
from pipeline.stages.thread_stage import run_thread_stage

logger = logging.getLogger(__name__)


def _get_code_version() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _content_hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def _generate_seed(date_context: date, run_id: uuid.UUID) -> int:
    # Keep seed within PostgreSQL BIGINT range.
    max_bigint = (2**63) - 1
    seed_value = int(
        hashlib.sha256(f"{date_context.isoformat()}{run_id}".encode()).hexdigest()[:16],
        16,
    )
    return seed_value % max_bigint


def _coerce_object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(dict(item))
    return out


def _coerce_object(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _signals_have_embeddings(signals: list[dict[str, Any]]) -> bool:
    for signal in signals:
        embedding = signal.get("embedding")
        if isinstance(embedding, list) and len(embedding) > 0:
            return True
    return False


def _strip_signal_embeddings(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped: list[dict[str, Any]] = []
    for signal in signals:
        cleaned = {
            key: value
            for key, value in signal.items()
            if key not in {"embedding", "_wild_card_distance"}
        }
        entities = cleaned.get("entities")
        if isinstance(entities, list):
            cleaned["entities"] = [str(entity).strip() for entity in entities if str(entity).strip()]
        else:
            cleaned["entities"] = []
        stripped.append(cleaned)
    return stripped


async def _resolve_parent_run(
    session: AsyncSession,
    *,
    date_context: date,
    regeneration_mode: RegenerationMode | None,
    parent_run_id: uuid.UUID | None,
) -> PipelineRun | None:
    if regeneration_mode in (None, RegenerationMode.FULL_RERUN):
        return None

    parent: PipelineRun | None = None
    if parent_run_id is not None:
        parent = await session.get(PipelineRun, parent_run_id)
    else:
        result = await session.execute(
            select(PipelineRun)
            .where(
                PipelineRun.date_context == date_context,
                PipelineRun.status == "completed",
            )
            .order_by(PipelineRun.run_number.desc())
            .limit(1)
        )
        parent = result.scalars().first()

    if parent is None:
        raise ValueError("Regeneration requires a completed parent run.")
    if parent.date_context != date_context:
        raise ValueError("Parent run date_context does not match the requested date.")
    return parent


async def _get_previous_thread_snapshot(session: AsyncSession, date_context: date) -> list[dict]:
    """Fallback: retrieve thread snapshot from the most recent successful run."""
    result = await session.execute(
        sa_text(
            "SELECT thread_snapshot FROM pipeline_runs "
            "WHERE status = 'completed' AND date_context < :dc "
            "ORDER BY date_context DESC, run_number DESC LIMIT 1"
        ),
        {"dc": date_context},
    )
    row = result.first()
    if row and row[0]:
        return row[0] if isinstance(row[0], list) else []
    return []


def _today_in_timezone(timezone_name: str) -> date:
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except Exception:
        return datetime.now(UTC).date()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _event_context_mode(*, date_context: date, today: date, settings: Any) -> tuple[str, int]:
    days_out = (date_context - today).days
    ephemeris_only_after = max(_safe_int(getattr(settings, "ephemeris_only_after_days", 3), 3), 0)
    thread_only_after = max(_safe_int(getattr(settings, "thread_only_after_days", 1), 1), 0)
    if thread_only_after > ephemeris_only_after:
        thread_only_after = ephemeris_only_after

    if days_out > ephemeris_only_after:
        return "ephemeris_only", days_out
    if days_out > thread_only_after:
        return "thread_only", days_out
    return "near_event", days_out


def _normalize_trigger_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, Any] = {}
    for key, raw in value.items():
        k = str(key).strip()
        if not k:
            continue
        if isinstance(raw, (str, int, float, bool)) or raw is None:
            out[k] = raw
        else:
            out[k] = str(raw)
    return out


def _parse_uuid(value: Any) -> uuid.UUID | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return uuid.UUID(text)
    except Exception:
        return None


def _event_type_label(event_type: str) -> str:
    return str(event_type or "").replace("_", " ").strip()


async def _load_event_context(
    session: AsyncSession,
    *,
    date_context: date,
    trigger_source: str,
    trigger_metadata: dict[str, Any],
    days_out: int,
) -> dict[str, Any] | None:
    if trigger_source != "manual_event":
        return None

    event: AstronomicalEvent | None = None
    source_event_id = _parse_uuid(trigger_metadata.get("source_event_id"))
    if source_event_id is not None:
        event = await session.get(AstronomicalEvent, source_event_id)

    if event is None:
        result = await session.execute(
            select(AstronomicalEvent)
            .where(func.date(AstronomicalEvent.at) == date_context)
            .order_by(AstronomicalEvent.at.asc())
            .limit(1)
        )
        event = result.scalars().first()

    if event is None:
        return {
            "date_context": date_context.isoformat(),
            "days_out": days_out,
            "event_label": "astronomical event",
        }

    body = str(event.body or "").strip()
    sign = str(event.sign or "").strip()
    event_label = _event_type_label(event.event_type)
    subject_parts = [part for part in [body, sign] if part]
    subject = " in ".join(subject_parts) if subject_parts else ""
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "event_label": event_label,
        "subject": subject,
        "body": body,
        "sign": sign,
        "at": event.at.isoformat(),
        "significance": str(event.significance or "").strip(),
        "date_context": date_context.isoformat(),
        "days_out": days_out,
    }


async def run_pipeline(
    date_context: date | None = None,
    regeneration_mode: RegenerationMode | None = None,
    parent_run_id: uuid.UUID | None = None,
    trigger_source: str = "scheduler",
    trigger_metadata: dict[str, Any] | None = None,
) -> uuid.UUID:
    settings = get_settings()
    if date_context is None:
        tz = ZoneInfo(settings.timezone)
        date_context = datetime.now(tz).date()
    normalized_trigger_metadata = _normalize_trigger_metadata(trigger_metadata)

    run_id = uuid.uuid4()
    seed = _generate_seed(date_context, run_id)
    run: PipelineRun | None = None
    lock_key = (
        int(hashlib.sha256(date_context.isoformat().encode()).hexdigest()[:15], 16) % (2**31)
    )
    engine = get_engine()

    # Hold a transaction-scoped advisory lock on a dedicated connection so it cannot leak
    # through pooled ORM sessions even if a pipeline session crashes.
    async with engine.connect() as lock_conn:
        lock_tx = await lock_conn.begin()
        try:
            result = await lock_conn.execute(
                sa_text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": lock_key},
            )
            if not result.scalar():
                raise RuntimeError(f"Could not acquire advisory lock for {date_context}")

            async with get_session() as session:
                # Load pipeline settings from DB (merged with defaults)
                ps = await load_pipeline_settings(session)

                try:
                    parent_run = await _resolve_parent_run(
                        session,
                        date_context=date_context,
                        regeneration_mode=regeneration_mode,
                        parent_run_id=parent_run_id,
                    )
                    parent_run_ref = parent_run.id if parent_run is not None else parent_run_id
                    if regeneration_mode == RegenerationMode.PROSE_ONLY and parent_run is not None:
                        # prose_only keeps the same seed and upstream artifacts; only synthesis changes.
                        seed = int(parent_run.seed)

                    existing = await session.execute(
                        sa_text(
                            "SELECT COALESCE(MAX(run_number), 0) "
                            "FROM pipeline_runs WHERE date_context = :dc"
                        ),
                        {"dc": date_context},
                    )
                    run_number = existing.scalar() + 1

                    initial_reused_artifacts: dict[str, Any] = {"trigger_source": trigger_source}
                    initial_reused_artifacts.update(normalized_trigger_metadata)
                    run = PipelineRun(
                        id=run_id, date_context=date_context, run_number=run_number,
                        started_at=datetime.now(UTC), status="running",
                        code_version=_get_code_version(), seed=seed,
                        template_versions={}, model_config_json=ps.model_dump(),
                        regeneration_mode=regeneration_mode.value if regeneration_mode else None,
                        parent_run_id=parent_run_ref,
                        reused_artifacts=initial_reused_artifacts,
                        ephemeris_json={}, distilled_signals={}, selected_signals={},
                        thread_snapshot={}, prompt_payloads={},
                        ephemeris_hash="", distillation_hash="", selection_hash="",
                    )
                    session.add(run)
                    await session.flush()
                    # Persist the run row immediately so fatal errors are still visible in admin history.
                    await session.commit()

                    reused_artifacts: dict[str, Any] = dict(initial_reused_artifacts)
                    event_mode = "default"
                    event_days_out = 0
                    event_context: dict[str, Any] | None = None
                    if trigger_source == "manual_event":
                        event_mode, event_days_out = _event_context_mode(
                            date_context=date_context,
                            today=_today_in_timezone(settings.timezone),
                            settings=ps.events,
                        )
                        event_context = await _load_event_context(
                            session,
                            date_context=date_context,
                            trigger_source=trigger_source,
                            trigger_metadata=normalized_trigger_metadata,
                            days_out=event_days_out,
                        )
                        reused_artifacts["event_mode"] = event_mode
                        reused_artifacts["event_days_out"] = event_days_out
                        if event_context is not None:
                            reused_artifacts["event_type"] = str(event_context.get("event_type", "")).strip()
                            source_event_id = str(event_context.get("id", "")).strip()
                            if source_event_id:
                                reused_artifacts["source_event_id"] = source_event_id

                    # Stage 1: Ephemeris
                    if regeneration_mode in (RegenerationMode.PROSE_ONLY, RegenerationMode.RESELECT):
                        if parent_run is None:
                            raise ValueError("Regeneration requested without a valid parent run.")
                        ephemeris_data = _coerce_object(parent_run.ephemeris_json)
                        if not ephemeris_data:
                            raise ValueError("Parent run is missing ephemeris artifacts.")
                        run.ephemeris_json = ephemeris_data
                        run.ephemeris_hash = parent_run.ephemeris_hash or _content_hash(ephemeris_data)
                        reused_artifacts["ephemeris_hash"] = run.ephemeris_hash
                    else:
                        ephemeris_data = await run_ephemeris_stage(date_context, session)
                        run.ephemeris_json = ephemeris_data
                        run.ephemeris_hash = _content_hash(ephemeris_data)
                    await session.commit()

                    # Stage 2/3: Ingestion + Distillation
                    sky_only = False
                    if regeneration_mode in (RegenerationMode.PROSE_ONLY, RegenerationMode.RESELECT):
                        if parent_run is None:
                            raise ValueError("Regeneration requested without a valid parent run.")
                        distilled = _coerce_object_list(parent_run.distilled_signals)
                        run.distilled_signals = distilled
                        run.distillation_hash = parent_run.distillation_hash or _content_hash(distilled)
                        reused_artifacts["distillation_hash"] = run.distillation_hash
                        sky_only = not bool(distilled)
                    else:
                        if trigger_source == "manual_event" and event_mode in {"ephemeris_only", "thread_only"}:
                            sky_only = True
                            distilled = []
                            logger.info(
                                "Skipping ingestion/distillation for event run_id=%s mode=%s days_out=%s",
                                run_id,
                                event_mode,
                                event_days_out,
                            )
                        else:
                            try:
                                raw_articles = await run_ingestion_stage(
                                    date_context,
                                    session,
                                    settings=ps.ingestion,
                                )
                                if not raw_articles:
                                    sky_only = True
                                    distilled = []
                                else:
                                    distilled = await run_distillation_stage(
                                        raw_articles, run_id, date_context, session, settings=ps.distillation,
                                    )
                            except Exception as e:
                                logger.error("Ingestion/distillation failed: %s", e)
                                sky_only = True
                                distilled = []
                        run.distilled_signals = _coerce_object_list(distilled)
                        run.distillation_hash = _content_hash(run.distilled_signals)
                    distilled = _coerce_object_list(distilled)
                    await session.commit()

                    # Stage 4/5: Embedding + Selection
                    if regeneration_mode == RegenerationMode.PROSE_ONLY:
                        if parent_run is None:
                            raise ValueError("prose_only regeneration requested without a parent run.")
                        selected = _strip_signal_embeddings(
                            _coerce_object_list(parent_run.selected_signals)
                        )
                        run.selected_signals = selected
                        run.selection_hash = parent_run.selection_hash or _content_hash(
                            {"selected": selected, "seed": seed}
                        )
                        reused_artifacts["selection_hash"] = run.selection_hash
                    else:
                        if distilled and not sky_only:
                            if not _signals_have_embeddings(distilled):
                                try:
                                    distilled = await run_embedding_stage(distilled, session)
                                except Exception as e:
                                    logger.warning("Embedding failed: %s", e)
                            selected = await run_selection_stage(
                                distilled,
                                seed,
                                settings=ps.selection,
                            )
                        else:
                            selected = []
                        selected = _strip_signal_embeddings(_coerce_object_list(selected))
                        if trigger_source == "manual_event":
                            if event_mode in {"ephemeris_only", "thread_only"}:
                                selected = []
                            elif event_mode == "near_event":
                                if bool(ps.events.major_signals_only_near_event):
                                    major_only = [
                                        s for s in selected
                                        if str(s.get("intensity", "")).strip().lower() == "major"
                                    ]
                                    if major_only:
                                        selected = major_only
                                selected = selected[: max(int(ps.events.max_signals_near_event), 0)]
                        run.selected_signals = selected
                        run.selection_hash = _content_hash({"selected": selected, "seed": seed})
                    await session.commit()

                    # Stage 6: Thread tracking
                    if regeneration_mode == RegenerationMode.PROSE_ONLY:
                        if parent_run is None:
                            raise ValueError("prose_only regeneration requested without a parent run.")
                        thread_snapshot = _coerce_object_list(parent_run.thread_snapshot)
                        reused_artifacts["thread_snapshot_hash"] = _content_hash(thread_snapshot)
                    else:
                        if trigger_source == "manual_event" and event_mode == "ephemeris_only":
                            thread_snapshot = []
                        else:
                            try:
                                thread_seed_signals = [] if (
                                    trigger_source == "manual_event" and event_mode == "thread_only"
                                ) else distilled
                                thread_snapshot = await run_thread_stage(
                                    thread_seed_signals,
                                    date_context,
                                    session,
                                    settings=ps.threads,
                                )
                            except Exception as e:
                                logger.warning("Thread tracking failed, using previous snapshot: %s", e)
                                thread_snapshot = await _get_previous_thread_snapshot(session, date_context)
                        if trigger_source == "manual_event":
                            if event_mode == "thread_only":
                                thread_snapshot = thread_snapshot[: max(int(ps.events.max_threads_thread_only), 0)]
                            elif event_mode == "near_event":
                                thread_snapshot = thread_snapshot[: max(int(ps.events.max_threads_near_event), 0)]
                    run.thread_snapshot = thread_snapshot
                    run.reused_artifacts = reused_artifacts
                    await session.commit()

                    # Stage 7: Synthesis (with fallback ladder)
                    synthesis_timeout_seconds = max(60, int(ps.synthesis.max_stage_seconds))
                    if trigger_source == "manual_event":
                        # Event-linked runs should resolve quickly for editorial workflow.
                        synthesis_timeout_seconds = min(synthesis_timeout_seconds, 300)
                    synthesis_sky_only = sky_only or not bool(selected)
                    synthesis_fast_mode = trigger_source == "manual_event"
                    run.prompt_payloads = {
                        "_status": "synthesis_in_progress",
                        "_telemetry": {
                            "trigger_source": trigger_source,
                            "fast_mode": synthesis_fast_mode,
                            "timeout_seconds": synthesis_timeout_seconds,
                            "sky_only": synthesis_sky_only,
                            "selected_signal_count": len(selected),
                            "thread_count": len(thread_snapshot),
                            "event_mode": event_mode if trigger_source == "manual_event" else None,
                            "event_days_out": event_days_out if trigger_source == "manual_event" else None,
                        },
                    }
                    await session.commit()
                    synthesis_started_at = datetime.now(UTC)
                    logger.info(
                        "Synthesis started run_id=%s date=%s source=%s fast_mode=%s timeout=%ss sky_only=%s selected=%d threads=%d",
                        run_id,
                        date_context,
                        trigger_source,
                        synthesis_fast_mode,
                        synthesis_timeout_seconds,
                        synthesis_sky_only,
                        len(selected),
                        len(thread_snapshot),
                    )
                    try:
                        synthesis_result = await asyncio.wait_for(
                            run_synthesis_stage(
                                ephemeris_data, selected, thread_snapshot, date_context, synthesis_sky_only, session,
                                settings=ps.synthesis,
                                allow_guard_relaxation=synthesis_fast_mode,
                                event_context=event_context,
                            ),
                            timeout=synthesis_timeout_seconds,
                        )
                        run.interpretive_plan = synthesis_result.get("interpretive_plan")
                        run.generated_output = synthesis_result.get("generated_output")
                        run.prompt_payloads = synthesis_result.get("prompt_payloads", {})
                        telemetry = run.prompt_payloads.get("_telemetry")
                        if not isinstance(telemetry, dict):
                            telemetry = {}
                            run.prompt_payloads["_telemetry"] = telemetry
                        telemetry.setdefault("trigger_source", trigger_source)
                        telemetry.setdefault("timeout_seconds", synthesis_timeout_seconds)
                        telemetry.setdefault("fast_mode", synthesis_fast_mode)
                        if trigger_source == "manual_event":
                            telemetry.setdefault("event_mode", event_mode)
                            telemetry.setdefault("event_days_out", event_days_out)
                        run.template_versions = synthesis_result.get("template_versions", {})
                        if run.generated_output is None and not run.error_detail:
                            run.error_detail = "Synthesis fell back to silence output after retries."

                        reading = Reading(
                            run_id=run_id, date_context=date_context, status="pending",
                            generated_standard=synthesis_result.get("standard_reading", SILENCE_READING),
                            generated_extended=synthesis_result.get(
                                "extended_reading",
                                {"title": "", "subtitle": "", "sections": [], "word_count": 0},
                            ),
                            generated_annotations=synthesis_result.get("annotations", []),
                        )
                        session.add(reading)
                        elapsed = int((datetime.now(UTC) - synthesis_started_at).total_seconds())
                        logger.info(
                            "Synthesis finished run_id=%s elapsed=%ss generated_output=%s",
                            run_id,
                            elapsed,
                            run.generated_output is not None,
                        )
                        await session.commit()
                    except Exception as e:
                        elapsed = int((datetime.now(UTC) - synthesis_started_at).total_seconds())
                        reading = Reading(
                            run_id=run_id, date_context=date_context, status="pending",
                            generated_standard=SILENCE_READING,
                            generated_extended={
                                "title": "",
                                "subtitle": "",
                                "sections": [],
                                "word_count": 0,
                            },
                            generated_annotations=[],
                        )
                        session.add(reading)
                        if isinstance(e, asyncio.TimeoutError):
                            logger.error(
                                "Synthesis timed out run_id=%s source=%s elapsed=%ss timeout=%ss",
                                run_id,
                                trigger_source,
                                elapsed,
                                synthesis_timeout_seconds,
                            )
                            run.error_detail = (
                                f"Synthesis stage exceeded {synthesis_timeout_seconds} seconds and was aborted."
                            )
                            run.prompt_payloads = {
                                "_status": "synthesis_timed_out",
                                "_telemetry": {
                                    "trigger_source": trigger_source,
                                    "fast_mode": synthesis_fast_mode,
                                    "timeout_seconds": synthesis_timeout_seconds,
                                    "elapsed_seconds": elapsed,
                                    "sky_only": synthesis_sky_only,
                                    "selected_signal_count": len(selected),
                                    "thread_count": len(thread_snapshot),
                                    "event_mode": event_mode if trigger_source == "manual_event" else None,
                                    "event_days_out": event_days_out if trigger_source == "manual_event" else None,
                                },
                            }
                        else:
                            logger.exception(
                                "Synthesis failed run_id=%s source=%s elapsed=%ss",
                                run_id,
                                trigger_source,
                                elapsed,
                            )
                            run.error_detail = str(e).strip() or "Synthesis stage failed unexpectedly."
                            run.prompt_payloads = {
                                "_status": "synthesis_failed",
                                "_telemetry": {
                                    "trigger_source": trigger_source,
                                    "fast_mode": synthesis_fast_mode,
                                    "timeout_seconds": synthesis_timeout_seconds,
                                    "elapsed_seconds": elapsed,
                                    "sky_only": synthesis_sky_only,
                                    "selected_signal_count": len(selected),
                                    "thread_count": len(thread_snapshot),
                                    "event_mode": event_mode if trigger_source == "manual_event" else None,
                                    "event_days_out": event_days_out if trigger_source == "manual_event" else None,
                                },
                                "_error": run.error_detail,
                            }
                        await session.commit()

                    # Stage 8: Publish
                    await run_publish_stage(reading, session, run)
                    run.status = "completed"
                    run.ended_at = datetime.now(UTC)
                    await session.commit()

                except Exception as e:
                    logger.exception("Pipeline failed: %s", e)
                    if run is not None:
                        try:
                            await session.rollback()
                            persisted_run = await session.get(PipelineRun, run_id)
                            if persisted_run is not None:
                                persisted_run.status = "failed"
                                persisted_run.error_detail = str(e)
                                persisted_run.ended_at = datetime.now(UTC)
                                await session.commit()
                        except Exception as persist_error:
                            logger.error("Could not persist failed run state for %s: %s", run_id, persist_error)
                    raise
        finally:
            if lock_tx.is_active:
                try:
                    await lock_tx.rollback()
                except Exception as unlock_error:
                    logger.warning("Could not close lock transaction cleanly: %s", unlock_error)

    return run_id
