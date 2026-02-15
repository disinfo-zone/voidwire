"""Simple login lockout guard for brute-force resistance."""

from __future__ import annotations

import time
from collections import defaultdict

FAIL_WINDOW_SECONDS = 15 * 60
FAIL_THRESHOLD = 8
BLOCK_SECONDS = 15 * 60

_failures: dict[str, list[float]] = defaultdict(list)
_blocked_until: dict[str, float] = {}


def _cleanup(now_ts: float) -> None:
    expired_blocks = [key for key, until in _blocked_until.items() if until <= now_ts]
    for key in expired_blocks:
        _blocked_until.pop(key, None)

    for key, timestamps in list(_failures.items()):
        recent = [ts for ts in timestamps if now_ts - ts <= FAIL_WINDOW_SECONDS]
        if recent:
            _failures[key] = recent
        else:
            _failures.pop(key, None)


async def is_login_blocked(scope: str, identifier: str) -> tuple[bool, int]:
    now_ts = time.time()
    _cleanup(now_ts)
    key = f"{scope}:{identifier}"
    blocked_until = _blocked_until.get(key)
    if blocked_until is None:
        return False, 0
    retry_after = max(1, int(blocked_until - now_ts))
    return retry_after > 0, retry_after


async def record_login_failure(scope: str, identifier: str) -> int:
    now_ts = time.time()
    _cleanup(now_ts)
    key = f"{scope}:{identifier}"
    series = _failures.setdefault(key, [])
    series.append(now_ts)
    series[:] = [ts for ts in series if now_ts - ts <= FAIL_WINDOW_SECONDS]
    count = len(series)
    if count >= FAIL_THRESHOLD:
        _blocked_until[key] = now_ts + BLOCK_SECONDS
    return count


async def clear_login_failures(scope: str, identifier: str) -> None:
    key = f"{scope}:{identifier}"
    _failures.pop(key, None)
    _blocked_until.pop(key, None)

