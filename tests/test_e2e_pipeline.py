"""End-to-end pipeline tests (with mocked LLM)."""

import pytest
from datetime import date

from pipeline.orchestrator import _content_hash, _generate_seed, SILENCE_READING


def test_silence_reading_has_required_fields():
    """Test that the silence reading template has all required fields."""
    assert "title" in SILENCE_READING
    assert "body" in SILENCE_READING
    assert len(SILENCE_READING["body"]) > 0


def test_content_hash_deterministic():
    """Test that content hashing is deterministic."""
    data = {"aspects": [{"body1": "mars", "body2": "saturn"}], "date": "2026-02-13"}
    h1 = _content_hash(data)
    h2 = _content_hash(data)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_content_hash_order_independent():
    """Test that content hash is independent of key order."""
    h1 = _content_hash({"a": 1, "b": 2})
    h2 = _content_hash({"b": 2, "a": 1})
    assert h1 == h2


def test_seed_generation():
    """Test that seed generation is deterministic and unique."""
    import uuid
    d = date(2026, 2, 13)
    run1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
    run2 = uuid.UUID("22222222-2222-2222-2222-222222222222")

    seed1a = _generate_seed(d, run1)
    seed1b = _generate_seed(d, run1)
    seed2 = _generate_seed(d, run2)

    assert seed1a == seed1b  # Same inputs -> same seed
    assert seed1a != seed2   # Different run_id -> different seed
    assert isinstance(seed1a, int)
    assert seed1a > 0
