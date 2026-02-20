from __future__ import annotations

from unittest.mock import patch

from api.services.birth_timezone import resolve_birth_timezone


def test_resolve_birth_timezone_uses_inferred_timezone_when_available():
    with patch(
        "api.services.birth_timezone.infer_birth_timezone",
        return_value="America/New_York",
    ):
        resolved, overridden = resolve_birth_timezone(
            latitude=33.0393,
            longitude=-85.0319,
            fallback_timezone="America/Los_Angeles",
        )

    assert resolved == "America/New_York"
    assert overridden is True


def test_resolve_birth_timezone_falls_back_when_inference_unavailable():
    with patch("api.services.birth_timezone.infer_birth_timezone", return_value=None):
        resolved, overridden = resolve_birth_timezone(
            latitude=33.0393,
            longitude=-85.0319,
            fallback_timezone="America/New_York",
        )

    assert resolved == "America/New_York"
    assert overridden is False

