"""Tests for pipeline orchestrator."""

import uuid
from datetime import date

import pytest

import pipeline.orchestrator as orchestrator
from pipeline.orchestrator import (
    _content_hash,
    _generate_seed,
    _is_duplicate_title,
    _regenerate_title,
    _strip_signal_embeddings,
)


def test_content_hash():
    h1 = _content_hash({"a": 1, "b": 2})
    h2 = _content_hash({"b": 2, "a": 1})
    assert h1 == h2


def test_generate_seed():
    run_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    d = date(2026, 2, 13)
    seed1 = _generate_seed(d, run_id)
    seed2 = _generate_seed(d, run_id)
    assert seed1 == seed2
    seed3 = _generate_seed(d, uuid.UUID("87654321-4321-8765-4321-876543218765"))
    assert seed1 != seed3


def test_strip_signal_embeddings():
    signals = [
        {"id": "s1", "summary": "alpha", "embedding": [0.1, 0.2], "entities": ["A", ""]},
        {"id": "s2", "summary": "beta", "_wild_card_distance": 0.5},
    ]
    stripped = _strip_signal_embeddings(signals)
    assert len(stripped) == 2
    assert "embedding" not in stripped[0]
    assert "_wild_card_distance" not in stripped[1]
    assert stripped[0]["entities"] == ["A"]


def test_is_duplicate_title_detects_fuzzy_similarity():
    recent_titles = [
        "The Architecture of Mist",
        "Harbor of Glass",
    ]
    assert _is_duplicate_title("Architecture of Mist", recent_titles) is True
    assert _is_duplicate_title("The Architecture of Mists", recent_titles) is True


def test_is_duplicate_title_allows_distinct_title():
    recent_titles = [
        "The Architecture of Mist",
        "Harbor of Glass",
    ]
    assert _is_duplicate_title("Ledger of Thunder", recent_titles) is False


@pytest.mark.asyncio
async def test_regenerate_title_retries_until_unique(monkeypatch):
    class DummyClient:
        def __init__(self):
            self.calls = 0

        async def generate(self, _slot, _messages, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return '{"title":"The Architecture of Mist"}'
            return '{"title":"Ledger Under Iron Rain"}'

        async def close(self):
            return None

    client = DummyClient()

    async def fake_get_llm_client(_session, _slot, timeout=30.0):
        assert timeout == 30.0
        return client

    monkeypatch.setattr(orchestrator, "_get_llm_client", fake_get_llm_client)
    title = await _regenerate_title(
        session=None,
        current_title="The Architecture of Mist",
        reading_body="Dense pressure and institutional fracture moves through the week.",
        recent_titles=["The Architecture of Mist", "Harbor of Glass"],
        date_context=date(2026, 2, 20),
    )
    assert title == "Ledger Under Iron Rain"
