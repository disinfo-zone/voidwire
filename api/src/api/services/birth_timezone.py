"""Birth-time timezone resolution from coordinates."""

from __future__ import annotations

from zoneinfo import ZoneInfo

try:
    from timezonefinder import TimezoneFinder
except Exception:  # pragma: no cover - dependency may be absent in some dev envs
    TimezoneFinder = None  # type: ignore[assignment]

_finder: TimezoneFinder | None = None


def _get_finder() -> TimezoneFinder | None:
    global _finder
    if TimezoneFinder is None:
        return None
    if _finder is None:
        _finder = TimezoneFinder(in_memory=True)
    return _finder


def infer_birth_timezone(*, latitude: float, longitude: float) -> str | None:
    """Infer IANA timezone for the given coordinates."""
    finder = _get_finder()
    if finder is None:
        return None

    timezone_name = finder.timezone_at(lng=longitude, lat=latitude)
    if not timezone_name:
        timezone_name = finder.certain_timezone_at(lng=longitude, lat=latitude)
    if not timezone_name:
        return None

    normalized = str(timezone_name).strip()
    if not normalized:
        return None

    try:
        ZoneInfo(normalized)
    except Exception:
        return None
    return normalized


def resolve_birth_timezone(
    *,
    latitude: float,
    longitude: float,
    fallback_timezone: str,
) -> tuple[str, bool]:
    """Resolve timezone from coordinates and indicate if fallback was overridden."""
    fallback = fallback_timezone.strip()
    inferred = infer_birth_timezone(latitude=latitude, longitude=longitude)
    if inferred:
        return inferred, inferred != fallback
    return fallback, False

