"""Template runtime behavior tests for synthesis stage."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from pipeline.stages.synthesis_stage import (
    _find_active_template,
    _prepare_signal_context,
    _prepare_thread_context,
    _render_prompt_template,
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
