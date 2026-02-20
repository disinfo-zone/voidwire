"""Template runtime behavior tests for synthesis stage."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from pipeline.stages.synthesis_stage import (
    _has_forbidden_timekeeping_lede,
    _find_active_template,
    _prepare_signal_context,
    _prepare_thread_context,
    _repair_forbidden_timekeeping_ledes,
    _render_prompt_template,
    _validate_prose,
)


def _tpl(name: str, version: int):
    return SimpleNamespace(id=uuid.uuid4(), template_name=name, version=version)


def test_find_active_template_prefers_exact_candidate() -> None:
    exact = _tpl("synthesis_prose", 2)
    prefixed = _tpl("synthesis_prose_custom", 9)
    active = {
        "synthesis_prose": exact,
        "synthesis_prose_custom": prefixed,
    }
    chosen = _find_active_template(active, ("synthesis_prose",), prefix="synthesis_prose")
    assert chosen is exact


def test_find_active_template_falls_back_to_highest_prefix_version() -> None:
    older = _tpl("synthesis_plan_custom", 1)
    newer = _tpl("synthesis_plan_v2", 2)
    active = {
        "synthesis_plan_custom": older,
        "synthesis_plan_v2": newer,
    }
    chosen = _find_active_template(active, ("missing_name",), prefix="synthesis_plan")
    assert chosen is newer


def test_render_prompt_template_serializes_values() -> None:
    prompt = "DATE={{date_context}}\nSIGNALS={{selected_signals}}\nMISSING={{missing}}"
    rendered = _render_prompt_template(
        prompt,
        {
            "date_context": "2026-02-14",
            "selected_signals": [{"summary": "pressure rises"}],
        },
    )
    assert "2026-02-14" in rendered
    assert '"summary": "pressure rises"' in rendered
    assert "{{missing}}" not in rendered


def test_prepare_signal_context_strips_embedding_and_limits() -> None:
    signals = [
        {
            "id": "sig_1",
            "domain": "economy",
            "intensity": "major",
            "directionality": "escalating",
            "summary": "pressure rises",
            "entities": ["Central Bank", "Treasury"],
            "source_refs": ["https://example.com/a"],
            "embedding": [0.1, 0.2, 0.3],
            "was_wild_card": False,
            "selection_weight": 0.9,
        },
        {
            "id": "sig_2",
            "summary": "second signal",
            "embedding": [0.9],
        },
    ]
    prepared = _prepare_signal_context(signals, limit=1)
    assert len(prepared) == 1
    assert prepared[0]["id"] == "sig_1"
    assert prepared[0]["summary"] == "pressure rises"
    assert "embedding" not in prepared[0]


def test_prepare_thread_context_limits_rows() -> None:
    threads = [
        {"id": "1", "canonical_summary": "first", "domain": "economy", "appearances": 3},
        {"id": "2", "canonical_summary": "second", "domain": "culture", "appearances": 1},
    ]
    prepared = _prepare_thread_context(threads, limit=1)
    assert len(prepared) == 1
    assert prepared[0]["id"] == "1"
    assert prepared[0]["appearances"] == 3


def test_validate_prose_allows_timekeeping_opening_for_post_repair_step() -> None:
    payload = {
        "standard_reading": {
            "title": "Signal Check",
            "body": "At seventeen minutes before the sixth hour by universal timekeeping, the pressure folds inward and hardens into pattern.",
            "word_count": 140,
        },
        "extended_reading": {
            "title": "Deep Cut",
            "subtitle": "Sub",
            "sections": [{"heading": "Arc", "body": "Pattern continues."}],
            "word_count": 220,
        },
        "transit_annotations": [],
    }

    _validate_prose(payload, mention_policy=None, guarded_entities=[])


def test_validate_prose_allows_direct_interpretive_opening() -> None:
    payload = {
        "standard_reading": {
            "title": "Signal Check",
            "body": "Pressure builds where memory and strategy collide, forcing old narratives into a sharper frame.",
            "word_count": 140,
        },
        "extended_reading": {
            "title": "Deep Cut",
            "subtitle": "Sub",
            "sections": [{"heading": "Arc", "body": "Pattern continues through institutions and language."}],
            "word_count": 220,
        },
        "transit_annotations": [],
    }

    _validate_prose(payload, mention_policy=None, guarded_entities=[])


@pytest.mark.asyncio
async def test_repair_forbidden_timekeeping_opening_with_llm_rewrite() -> None:
    class DummyClient:
        async def generate(self, _slot, _messages, **_kwargs):
            return (
                '{"opening":"Pressure gathers where old routines can no longer hold, and the day asks '
                'for precise choices before momentum hardens."}'
            )

    payload = {
        "standard_reading": {
            "title": "Signal Check",
            "body": (
                "At seventeen minutes before the sixth hour by universal timekeeping, the pressure "
                "folds inward and hardens into pattern. The rest of the reading continues here."
            ),
            "word_count": 140,
        },
        "extended_reading": {"title": "", "subtitle": "", "sections": [], "word_count": 0},
        "transit_annotations": [],
    }

    repaired, metadata = await _repair_forbidden_timekeeping_ledes(
        result=payload,
        client=DummyClient(),
        date_context=date(2026, 2, 20),
        mention_policy={},
        guarded_entities=[],
        banned_phrases=[],
    )

    new_body = repaired["standard_reading"]["body"]
    assert isinstance(metadata, dict)
    assert metadata.get("applied") is True
    assert metadata.get("changes")
    assert not _has_forbidden_timekeeping_lede(new_body)
    assert new_body.startswith("Pressure gathers where old routines can no longer hold")


@pytest.mark.asyncio
async def test_repair_forbidden_timekeeping_opening_falls_back_when_llm_fails() -> None:
    class FailingClient:
        async def generate(self, _slot, _messages, **_kwargs):
            raise RuntimeError("LLM unavailable")

    payload = {
        "standard_reading": {
            "title": "Signal Check",
            "body": (
                "At 05:43 UTC, old pressure returns to the surface and pulls harder than expected. "
                "The rest of the reading continues here."
            ),
            "word_count": 140,
        },
        "extended_reading": {"title": "", "subtitle": "", "sections": [], "word_count": 0},
        "transit_annotations": [],
    }

    repaired, metadata = await _repair_forbidden_timekeeping_ledes(
        result=payload,
        client=FailingClient(),
        date_context=date(2026, 2, 20),
        mention_policy={},
        guarded_entities=[],
        banned_phrases=[],
    )

    new_body = repaired["standard_reading"]["body"]
    assert isinstance(metadata, dict)
    assert metadata.get("applied") is True
    assert metadata.get("changes")[0]["method"] == "deterministic_fallback"
    assert not _has_forbidden_timekeeping_lede(new_body)
