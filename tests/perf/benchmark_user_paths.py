"""Lightweight concurrent benchmarks for natal + personal reading paths.

Usage:
  python tests/perf/benchmark_user_paths.py
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from api.services.personal_reading_service import PersonalReadingService
from ephemeris.natal import calculate_natal_chart
from voidwire.services.pipeline_settings import PipelineSettings


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentile)))
    return ordered[index]


def _summarize(durations: list[float]) -> dict[str, float]:
    total = sum(durations)
    count = len(durations)
    return {
        "count": float(count),
        "total_seconds": round(total, 4),
        "avg_ms": round((total / count) * 1000, 2) if count else 0.0,
        "p50_ms": round(_percentile(durations, 0.50) * 1000, 2),
        "p95_ms": round(_percentile(durations, 0.95) * 1000, 2),
        "max_ms": round(max(durations) * 1000, 2) if durations else 0.0,
        "throughput_rps": round((count / total), 2) if total > 0 else 0.0,
    }


async def _run_concurrent(
    *,
    total_requests: int,
    concurrency: int,
    fn: Callable[[int], Awaitable[None]],
) -> list[float]:
    semaphore = asyncio.Semaphore(concurrency)
    durations: list[float] = []

    async def _one(index: int) -> None:
        async with semaphore:
            start = time.perf_counter()
            await fn(index)
            durations.append(time.perf_counter() - start)

    await asyncio.gather(*(_one(i) for i in range(total_requests)))
    return durations


async def run_natal_benchmark(total_requests: int, concurrency: int) -> dict[str, float]:
    async def _invoke(_: int) -> None:
        await asyncio.to_thread(
            calculate_natal_chart,
            birth_date=date(1990, 5, 5),
            birth_time=None,
            birth_latitude=40.7128,
            birth_longitude=-74.0060,
            birth_timezone="America/New_York",
            house_system="placidus",
        )

    durations = await _run_concurrent(
        total_requests=total_requests,
        concurrency=concurrency,
        fn=_invoke,
    )
    return _summarize(durations)


class _FakeDB:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        return

    async def rollback(self) -> None:
        return


class _FakeLLMClient:
    async def close(self) -> None:
        return


async def run_personal_reading_benchmark(
    total_requests: int,
    concurrency: int,
) -> dict[str, float]:
    chart = calculate_natal_chart(
        birth_date=date(1990, 5, 5),
        birth_time=None,
        birth_latitude=40.7128,
        birth_longitude=-74.0060,
        birth_timezone="America/New_York",
        house_system="placidus",
    )
    user = SimpleNamespace(id=uuid.uuid4())
    profile = SimpleNamespace(
        birth_date=date(1990, 5, 5),
        birth_time=None,
        birth_latitude=40.7128,
        birth_longitude=-74.0060,
        birth_timezone="America/New_York",
        house_system="placidus",
        natal_chart_json=chart,
    )
    db = _FakeDB()

    async def _fake_generate_with_validation(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        return {
            "title": "Daily Personal Reading",
            "body": "A concise benchmark payload",
            "sections": [],
            "word_count": 80,
        }

    async def _invoke(_: int) -> None:
        reading = await PersonalReadingService._generate_reading(
            user=user,
            profile=profile,
            db=db,  # type: ignore[arg-type]
            tier="pro",
            target_date=date.today(),
        )
        if reading is None:
            raise RuntimeError("Personal reading benchmark run returned no reading")

    with (
        patch(
            "api.services.personal_reading_service._build_llm_client",
            new=AsyncMock(return_value=_FakeLLMClient()),
        ),
        patch(
            "api.services.personal_reading_service._get_today_ephemeris",
            new=AsyncMock(
                return_value={
                    "positions": {
                        "sun": {"longitude": 325.1},
                        "moon": {"longitude": 102.4},
                        "mercury": {"longitude": 300.0},
                    }
                }
            ),
        ),
        patch(
            "api.services.personal_reading_service._get_today_reading_context",
            new=AsyncMock(return_value={"title": "Daily", "body": "Context"}),
        ),
        patch(
            "api.services.personal_reading_service.generate_with_validation",
            new=AsyncMock(side_effect=_fake_generate_with_validation),
        ),
        patch(
            "api.services.personal_reading_service.load_pipeline_settings",
            new=AsyncMock(return_value=PipelineSettings()),
        ),
    ):
        durations = await _run_concurrent(
            total_requests=total_requests,
            concurrency=concurrency,
            fn=_invoke,
        )
    return _summarize(durations)


def _print_summary(name: str, summary: dict[str, float]) -> None:
    print(f"{name}:")
    for key in (
        "count",
        "total_seconds",
        "avg_ms",
        "p50_ms",
        "p95_ms",
        "max_ms",
        "throughput_rps",
    ):
        print(f"  {key}: {summary[key]}")
    print()


async def _main_async(total_requests: int, concurrency: int) -> dict[str, float]:
    natal = await run_natal_benchmark(total_requests, concurrency)
    personal = await run_personal_reading_benchmark(total_requests, concurrency)
    _print_summary("natal_chart", natal)
    _print_summary("personal_reading", personal)

    p95_values = [natal["p95_ms"], personal["p95_ms"]]
    combined_mean = round(statistics.mean(p95_values), 2)
    print(f"combined_p95_ms_mean: {combined_mean}")
    return {
        "natal_p95_ms": natal["p95_ms"],
        "personal_p95_ms": personal["p95_ms"],
        "combined_p95_ms_mean": combined_mean,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run user-path performance benchmarks.")
    parser.add_argument("--requests", type=int, default=40, help="Total requests per benchmark")
    parser.add_argument("--concurrency", type=int, default=8, help="Concurrent workers")
    parser.add_argument(
        "--max-natal-p95-ms",
        type=float,
        default=0.0,
        help="Fail if natal_chart p95 exceeds this threshold (0 disables)",
    )
    parser.add_argument(
        "--max-personal-p95-ms",
        type=float,
        default=0.0,
        help="Fail if personal_reading p95 exceeds this threshold (0 disables)",
    )
    parser.add_argument(
        "--max-combined-p95-mean-ms",
        type=float,
        default=0.0,
        help="Fail if combined p95 mean exceeds this threshold (0 disables)",
    )
    args = parser.parse_args()
    metrics = asyncio.run(_main_async(total_requests=args.requests, concurrency=args.concurrency))

    failures: list[str] = []
    if args.max_natal_p95_ms > 0 and metrics["natal_p95_ms"] > args.max_natal_p95_ms:
        failures.append(f"natal_chart p95 {metrics['natal_p95_ms']}ms > {args.max_natal_p95_ms}ms")
    if args.max_personal_p95_ms > 0 and metrics["personal_p95_ms"] > args.max_personal_p95_ms:
        failures.append(
            f"personal_reading p95 {metrics['personal_p95_ms']}ms > {args.max_personal_p95_ms}ms"
        )
    if (
        args.max_combined_p95_mean_ms > 0
        and metrics["combined_p95_ms_mean"] > args.max_combined_p95_mean_ms
    ):
        failures.append(
            "combined p95 mean "
            f"{metrics['combined_p95_ms_mean']}ms > {args.max_combined_p95_mean_ms}ms"
        )

    if failures:
        for failure in failures:
            print(f"PERF REGRESSION: {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
