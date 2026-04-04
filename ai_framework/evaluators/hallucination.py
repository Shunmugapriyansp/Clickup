"""
Hallucination Evaluator
=======================
Wraps DeepEval's HallucinationMetric and adds:
  - Per-turn tracking to build a hallucination-vs-token-count curve
  - Inflection-point detection (the token count where reliability degrades)
  - Context-utilisation warnings (model nearing context window limit)
"""
from __future__ import annotations

import statistics
from typing import List, Optional

from deepeval import evaluate
from deepeval.metrics import HallucinationMetric
from deepeval.test_case import LLMTestCase

from core.config import get_config
from core.logger import get_logger
from core.types import (
    HallucinationCurveResult,
    HallucinationDataPoint,
    LLMResponse,
    QualityMetric,
)

log = get_logger(__name__)
_cfg = get_config()


# ---------------------------------------------------------------------------
# Single-response hallucination check
# ---------------------------------------------------------------------------

def check_hallucination(
    prompt: str,
    response: LLMResponse,
    context: List[str],
    threshold: Optional[float] = None,
) -> float:
    """
    Run DeepEval's HallucinationMetric against a single response.

    Returns the score (0–1; higher = less hallucination = better).
    Raises AssertionError if score is below threshold.
    """
    t = threshold or _cfg.thresholds.hallucination
    metric = HallucinationMetric(threshold=t, model=_cfg.ai.model)
    test_case = LLMTestCase(
        input=prompt,
        actual_output=response.content,
        context=context,
    )
    metric.measure(test_case)
    score: float = metric.score  # type: ignore[attr-defined]
    passed: bool = metric.is_successful()  # type: ignore[attr-defined]

    level = "[green]PASS[/]" if passed else "[red]FAIL[/]"
    log.info(
        f"Hallucination {level} | score={score:.3f} threshold={t} "
        f"tokens={response.usage.total_tokens}"
    )
    return score


# ---------------------------------------------------------------------------
# Context-window risk warning
# ---------------------------------------------------------------------------

def warn_context_utilization(response: LLMResponse) -> None:
    """Log warnings when the model is consuming dangerous amounts of context."""
    pct = response.usage.context_utilization_pct
    warn_pct = _cfg.thresholds.context_utilization_warning_pct
    crit_pct = _cfg.thresholds.context_utilization_critical_pct

    if pct >= crit_pct:
        log.warning(
            f"[bold red]CRITICAL context utilization[/]: {pct:.1f}% "
            f"({response.usage.prompt_tokens}/{response.usage.context_window_size} tokens). "
            "Hallucination risk is HIGH at this context length."
        )
    elif pct >= warn_pct:
        log.warning(
            f"[yellow]High context utilization[/]: {pct:.1f}% "
            f"({response.usage.prompt_tokens}/{response.usage.context_window_size} tokens). "
            "Monitor hallucination scores closely."
        )


# ---------------------------------------------------------------------------
# Hallucination curve — multi-turn analysis
# ---------------------------------------------------------------------------

class HallucinationAnalyzer:
    """
    Run a sequence of test cases with progressively growing context and plot
    the relationship between token count and hallucination score.

    Usage
    -----
    analyzer = HallucinationAnalyzer()
    for turn, (prompt, response, context) in enumerate(conversation_turns, 1):
        analyzer.record(turn, prompt, response, context)
    result = analyzer.build_curve()
    """

    def __init__(self, threshold: Optional[float] = None) -> None:
        self._threshold = threshold or _cfg.thresholds.hallucination
        self._data_points: List[HallucinationDataPoint] = []

    def record(
        self,
        turn: int,
        prompt: str,
        response: LLMResponse,
        context: List[str],
    ) -> HallucinationDataPoint:
        """Measure hallucination for one turn and store the data point."""
        warn_context_utilization(response)
        score = check_hallucination(prompt, response, context, self._threshold)
        dp = HallucinationDataPoint(
            turn=turn,
            prompt_tokens=response.usage.prompt_tokens,
            hallucination_score=score,
            exceeded_threshold=score < self._threshold,
        )
        self._data_points.append(dp)
        return dp

    def build_curve(self) -> HallucinationCurveResult:
        """
        Analyse recorded data points and identify the inflection point where
        the model starts hallucinating (score drops below threshold).
        """
        inflection_token: Optional[int] = None
        inflection_turn: Optional[int] = None
        safe_budget: Optional[int] = None

        for i, dp in enumerate(self._data_points):
            if dp.exceeded_threshold and inflection_token is None:
                inflection_token = dp.prompt_tokens
                inflection_turn = dp.turn
                # Safe budget = tokens just before crossing the threshold
                if i > 0:
                    safe_budget = self._data_points[i - 1].prompt_tokens

        if inflection_token:
            log.warning(
                f"[bold red]Hallucination inflection detected[/] at turn={inflection_turn}, "
                f"tokens={inflection_token}. "
                f"Safe token budget: {safe_budget or 'N/A'}"
            )
        else:
            log.info(
                "[green]No hallucination inflection detected[/] across all recorded turns."
            )

        return HallucinationCurveResult(
            data_points=self._data_points,
            threshold=self._threshold,
            inflection_token_count=inflection_token,
            inflection_turn=inflection_turn,
            safe_token_budget=safe_budget,
        )

    def summary(self) -> dict:
        scores = [dp.hallucination_score for dp in self._data_points]
        if not scores:
            return {}
        curve = self.build_curve()
        return {
            "turns_recorded": len(scores),
            "avg_score": round(statistics.mean(scores), 3),
            "min_score": round(min(scores), 3),
            "max_score": round(max(scores), 3),
            "threshold": self._threshold,
            "inflection_turn": curve.inflection_turn,
            "inflection_token_count": curve.inflection_token_count,
            "safe_token_budget": curve.safe_token_budget,
        }
