"""
Performance Baseline Manager
=============================
Loads baselines from fixtures/performance_baselines.json and exposes
them for use in LatencyTracker.assert_slo() comparisons.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from core.logger import get_logger
from core.types import PerformanceBaseline

log = get_logger(__name__)

_DEFAULT_BASELINES_PATH = Path(__file__).parent.parent / "fixtures" / "performance_baselines.json"


def load_baselines(path: Optional[Path] = None) -> Dict[str, PerformanceBaseline]:
    """Load all baselines from the JSON file. Returns empty dict on missing file."""
    fpath = path or _DEFAULT_BASELINES_PATH
    if not fpath.exists():
        log.debug(f"No baselines file found at {fpath} — returning empty dict.")
        return {}
    with fpath.open() as f:
        raw: dict = json.load(f)
    result: Dict[str, PerformanceBaseline] = {}
    for name, data in raw.items():
        result[name] = PerformanceBaseline(
            name=name,
            p50_latency_ms=data.get("p50_latency_ms", 1000),
            p95_latency_ms=data.get("p95_latency_ms", 5000),
            p99_latency_ms=data.get("p99_latency_ms", 10000),
            min_tokens_per_second=data.get("min_tokens_per_second", 10),
            max_cost_per_1k_tokens_usd=data.get("max_cost_per_1k_tokens_usd", 0.02),
        )
    log.debug(f"Loaded {len(result)} performance baselines from {fpath}")
    return result


def get_baseline(name: str, path: Optional[Path] = None) -> Optional[PerformanceBaseline]:
    return load_baselines(path).get(name)
