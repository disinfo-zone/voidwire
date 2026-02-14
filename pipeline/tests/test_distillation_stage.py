"""Tests for distillation signal normalization."""

import uuid
from datetime import date

import pytest

from pipeline.stages import distillation_stage
from pipeline.stages.distillation_stage import _normalize_signal, _to_string_list


def test_to_string_list_coerces_scalar_and_list_values():
    assert _to_string_list(None) == []
    assert _to_string_list("a") == ["a"]
    assert _to_string_list(["a", 2, "  "]) == ["a", "2"]
    assert _to_string_list((1, "x")) == ["1", "x"]


def test_normalize_signal_coerces_and_applies_safe_defaults():
    normalized = _normalize_signal(
        {
            "summary": "  Test signal  ",
            "domain": "politics",  # invalid for schema -> fallback
            "intensity": "urgent",  # invalid -> fallback
            "directionality": "spiking",  # invalid -> fallback
            "entities": ["A", 42],
            "source_refs": [1, 2, "article-3"],
        }
    )

    assert normalized["summary"] == "Test signal"
    assert normalized["domain"] == "anomalous"
    assert normalized["intensity"] == "minor"
    assert normalized["directionality"] == "stable"
    assert normalized["entities"] == ["A", "42"]
    assert normalized["source_refs"] == ["1", "2", "article-3"]


@pytest.mark.asyncio
async def test_run_distillation_stage_signal_ids_are_unique_per_run(monkeypatch):
    class DummyClient:
        async def close(self):
            return None

    class DummySession:
        def add(self, _obj):
            return None

    async def fake_get_llm_client(_session, _slot):
        return DummyClient()

    async def fake_generate(_client, _slot, _messages, _validator):
        return [{"summary": "Signal A"}]

    monkeypatch.setattr(distillation_stage, "_get_llm_client", fake_get_llm_client)
    monkeypatch.setattr(distillation_stage, "generate_with_validation", fake_generate)

    run_id = uuid.uuid4()
    signals = await distillation_stage.run_distillation_stage(
        articles=[{"title": "A1", "domain": "technology"}],
        run_id=run_id,
        date_context=date(2026, 2, 14),
        session=DummySession(),
    )

    assert signals[0]["id"].startswith(f"sig_20260214_{run_id.hex[:8]}_")
