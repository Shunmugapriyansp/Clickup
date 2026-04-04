"""
Quality Report Writer
=====================
Appends QualityMetric records to a time-series JSON file so quality
regressions are visible across CI runs.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.config import get_config
from core.logger import get_logger
from core.types import QualityMetric

log = get_logger(__name__)
_cfg = get_config()


def _default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class QualityReporter:
    """
    Write and read per-run quality metrics.

    Usage
    -----
    reporter = QualityReporter()
    reporter.record(metric)
    reporter.assert_no_regression(metric, baseline_name="chat_api")
    reporter.save()
    """

    def __init__(self, report_path: Optional[Path] = None) -> None:
        self._path = report_path or Path(_cfg.reports_dir) / "ai_quality_metrics.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._current_run: List[QualityMetric] = []

        # Load existing history
        self._history: list = []
        if self._path.exists():
            try:
                with self._path.open() as f:
                    self._history = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._history = []

    def record(self, metric: QualityMetric) -> None:
        self._current_run.append(metric)
        log.info(
            f"Quality metric recorded | test={metric.test_name} "
            f"hallucination={metric.hallucination_score:.2f} "
            f"relevancy={metric.relevancy_score:.2f} "
            f"task_complete={metric.task_completion}"
        )

    def save(self) -> None:
        """Append current run metrics to the history file."""
        run_entry = {
            "run_timestamp": datetime.utcnow().isoformat(),
            "metrics": [asdict(m) for m in self._current_run],
        }
        self._history.append(run_entry)
        with self._path.open("w") as f:
            json.dump(self._history, f, indent=2, default=_default)
        log.info(f"Quality report saved → {self._path} ({len(self._current_run)} metrics)")

    def assert_no_regression(
        self,
        metric: QualityMetric,
        hallucination_min: Optional[float] = None,
        relevancy_min: Optional[float] = None,
        faithfulness_min: Optional[float] = None,
    ) -> None:
        """Assert quality scores meet minimums. Raises AssertionError on failure."""
        failures: list = []
        h_min = hallucination_min or _cfg.thresholds.hallucination
        r_min = relevancy_min or _cfg.thresholds.relevancy
        f_min = faithfulness_min or _cfg.thresholds.faithfulness

        if metric.hallucination_score < h_min:
            failures.append(
                f"hallucination_score {metric.hallucination_score:.3f} < {h_min}"
            )
        if metric.relevancy_score < r_min:
            failures.append(
                f"relevancy_score {metric.relevancy_score:.3f} < {r_min}"
            )
        if metric.faithfulness_score < f_min:
            failures.append(
                f"faithfulness_score {metric.faithfulness_score:.3f} < {f_min}"
            )

        if failures:
            raise AssertionError(
                f"Quality regression detected for '{metric.test_name}':\n  "
                + "\n  ".join(failures)
            )

        log.info(f"[green]Quality check passed[/] for '{metric.test_name}'")
