"""
Latency Tracker
===============
Records latency samples from AI API calls and computes percentile statistics.
Compares results against configurable baselines and SLO thresholds.
"""
from __future__ import annotations

import statistics
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, List, Optional

from core.config import get_config
from core.logger import get_logger
from core.types import LatencySample, PerformanceBaseline, PerformanceReport

log = get_logger(__name__)
_cfg = get_config()


def _percentile(data: List[float], pct: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(sorted_data) - 1)
    return round(sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f), 2)


class LatencyTracker:
    """
    Collect latency samples, compute statistics, and assert against SLOs.

    Example
    -------
    tracker = LatencyTracker("chat_api")
    for _ in range(10):
        with tracker.measure() as t:
            response = client.chat(messages)
            t.completion_tokens = response.usage.completion_tokens
        tracker.record_response(response)
    report = tracker.build_report()
    tracker.assert_slo()
    """

    def __init__(
        self,
        test_name: str,
        baseline: Optional[PerformanceBaseline] = None,
    ) -> None:
        self._test_name = test_name
        self._baseline = baseline
        self._samples: List[LatencySample] = []

    @contextmanager
    def measure(self) -> Generator["_Timer", None, None]:
        """Context manager that auto-records wall-clock latency."""
        timer = _Timer()
        timer._start = time.perf_counter()
        yield timer
        timer.latency_ms = (time.perf_counter() - timer._start) * 1000
        self._samples.append(
            LatencySample(
                timestamp=datetime.utcnow(),
                latency_ms=timer.latency_ms,
                ttfb_ms=timer.ttfb_ms,
                tokens_per_second=timer.tokens_per_second,
                prompt_tokens=timer.prompt_tokens,
                completion_tokens=timer.completion_tokens,
            )
        )
        log.debug(
            f"Sample recorded: latency={timer.latency_ms:.0f}ms "
            f"tps={timer.tokens_per_second:.1f}"
        )

    def add_sample_from_response(self, response) -> None:  # LLMResponse
        """Add a pre-captured LLMResponse sample directly."""
        self._samples.append(
            LatencySample(
                timestamp=response.timestamp,
                latency_ms=response.latency_ms,
                ttfb_ms=response.ttfb_ms,
                tokens_per_second=response.tokens_per_second,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )
        )

    def build_report(self) -> PerformanceReport:
        latencies = [s.latency_ms for s in self._samples]
        tps_list = [s.tokens_per_second for s in self._samples if s.tokens_per_second > 0]

        report = PerformanceReport(
            test_name=self._test_name,
            samples=self._samples,
            p50_ms=_percentile(latencies, 50),
            p95_ms=_percentile(latencies, 95),
            p99_ms=_percentile(latencies, 99),
            avg_tokens_per_second=round(statistics.mean(tps_list), 2) if tps_list else 0.0,
            baseline=self._baseline,
        )
        return report

    def assert_slo(
        self,
        p95_threshold_ms: Optional[float] = None,
        p99_threshold_ms: Optional[float] = None,
        min_tps: Optional[float] = None,
    ) -> None:
        """Assert that performance metrics meet the configured or provided SLOs."""
        p95_limit = p95_threshold_ms or _cfg.performance.p95_latency_threshold_ms
        p99_limit = p99_threshold_ms or _cfg.performance.p99_latency_threshold_ms
        tps_min = min_tps or _cfg.performance.min_tokens_per_second

        report = self.build_report()
        violations: list = []

        if report.p95_ms > p95_limit:
            violations.append(f"P95 latency {report.p95_ms}ms > SLO {p95_limit}ms")
        if report.p99_ms > p99_limit:
            violations.append(f"P99 latency {report.p99_ms}ms > SLO {p99_limit}ms")
        if report.avg_tokens_per_second < tps_min:
            violations.append(
                f"Avg tokens/sec {report.avg_tokens_per_second} < minimum {tps_min}"
            )

        if violations:
            raise AssertionError(
                f"Performance SLO violations for '{self._test_name}':\n  "
                + "\n  ".join(violations)
            )

        log.info(
            f"[green]SLO passed[/] | p50={report.p50_ms}ms p95={report.p95_ms}ms "
            f"p99={report.p99_ms}ms tps={report.avg_tokens_per_second}"
        )

    def to_dict(self) -> dict:
        r = self.build_report()
        return {
            "test_name": r.test_name,
            "sample_count": len(r.samples),
            "p50_ms": r.p50_ms,
            "p95_ms": r.p95_ms,
            "p99_ms": r.p99_ms,
            "avg_tokens_per_second": r.avg_tokens_per_second,
            "slo_p95_ms": _cfg.performance.p95_latency_threshold_ms,
            "slo_p99_ms": _cfg.performance.p99_latency_threshold_ms,
        }


class _Timer:
    """Mutable holder for timing data inside the measure() context manager."""
    def __init__(self) -> None:
        self._start: float = 0.0
        self.latency_ms: float = 0.0
        self.ttfb_ms: float = 0.0
        self.tokens_per_second: float = 0.0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
