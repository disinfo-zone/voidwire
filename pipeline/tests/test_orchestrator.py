"""Tests for pipeline orchestrator."""

import uuid
from datetime import date

from pipeline.orchestrator import _content_hash, _generate_seed, _strip_signal_embeddings


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
