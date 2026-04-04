"""
Token Utilization Tracker
==========================
Tracks token consumption across a conversation or test suite and flags:
  - Context window utilisation % per turn
  - Cost accumulation
  - Token efficiency (output density vs. input cost)
  - Risk zones where hallucination is more likely (>70% / >85% context used)
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import List, Optional

from core.config import get_config
from core.logger import get_logger
from core.types import LLMResponse, TokenUsage

log = get_logger(__name__)
_cfg = get_config()


@dataclass
class TurnTokenSnapshot:
    turn: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    context_utilization_pct: float
    estimated_cost_usd: float
    tokens_per_second: float
    risk_level: str  # "safe" | "warning" | "critical"


@dataclass
class TokenUtilizationReport:
    model: str
    context_window_size: int
    snapshots: List[TurnTokenSnapshot]
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_context_utilization_pct: float = 0.0
    peak_context_utilization_pct: float = 0.0
    efficiency_ratio: float = 0.0         # completion_tokens / prompt_tokens
    warning_turns: List[int] = field(default_factory=list)
    critical_turns: List[int] = field(default_factory=list)
    predicted_max_safe_turns: Optional[int] = None


class TokenTracker:
    """
    Attach to a ConversationRunner or use standalone to record token usage.

    Example
    -------
    tracker = TokenTracker(model="gpt-4o")
    for turn, response in enumerate(responses, 1):
        tracker.record(turn, response)
    report = tracker.build_report()
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self._model = model or _cfg.ai.model
        self._ctx_window = _cfg.ai.context_window_for(self._model)
        self._snapshots: List[TurnTokenSnapshot] = []

    def record(self, turn: int, response: LLMResponse) -> TurnTokenSnapshot:
        usage = response.usage
        pct = usage.context_utilization_pct
        warn_pct = _cfg.thresholds.context_utilization_warning_pct
        crit_pct = _cfg.thresholds.context_utilization_critical_pct

        if pct >= crit_pct:
            risk = "critical"
        elif pct >= warn_pct:
            risk = "warning"
        else:
            risk = "safe"

        snap = TurnTokenSnapshot(
            turn=turn,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            context_utilization_pct=pct,
            estimated_cost_usd=usage.estimated_cost_usd,
            tokens_per_second=response.tokens_per_second,
            risk_level=risk,
        )
        self._snapshots.append(snap)

        if risk == "critical":
            log.warning(
                f"[bold red]Turn {turn}[/] context at {pct:.1f}% "
                f"({usage.prompt_tokens}/{self._ctx_window}). "
                "Consider summarising or truncating conversation history."
            )
        elif risk == "warning":
            log.warning(
                f"[yellow]Turn {turn}[/] context at {pct:.1f}% — approaching limit."
            )

        return snap

    def build_report(self) -> TokenUtilizationReport:
        if not self._snapshots:
            return TokenUtilizationReport(
                model=self._model,
                context_window_size=self._ctx_window,
                snapshots=[],
            )

        total_prompt = sum(s.prompt_tokens for s in self._snapshots)
        total_completion = sum(s.completion_tokens for s in self._snapshots)
        total_cost = sum(s.estimated_cost_usd for s in self._snapshots)
        pcts = [s.context_utilization_pct for s in self._snapshots]
        warn_turns = [s.turn for s in self._snapshots if s.risk_level == "warning"]
        crit_turns = [s.turn for s in self._snapshots if s.risk_level == "critical"]

        efficiency = (total_completion / total_prompt) if total_prompt > 0 else 0.0

        # Naive linear prediction: if turns 1..N used X% on average, extrapolate to 100%
        avg_pct_per_turn = statistics.mean(pcts) if pcts else 0
        max_safe_turns: Optional[int] = None
        warn_threshold = _cfg.thresholds.context_utilization_warning_pct
        if avg_pct_per_turn > 0:
            max_safe_turns = int(warn_threshold / avg_pct_per_turn)

        report = TokenUtilizationReport(
            model=self._model,
            context_window_size=self._ctx_window,
            snapshots=self._snapshots,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_cost_usd=round(total_cost, 6),
            avg_context_utilization_pct=round(statistics.mean(pcts), 2),
            peak_context_utilization_pct=round(max(pcts), 2),
            efficiency_ratio=round(efficiency, 3),
            warning_turns=warn_turns,
            critical_turns=crit_turns,
            predicted_max_safe_turns=max_safe_turns,
        )

        log.info(
            f"Token report | model={self._model} turns={len(self._snapshots)} "
            f"total_tokens={total_prompt + total_completion} cost=${total_cost:.4f} "
            f"efficiency={efficiency:.2f} max_safe_turns={max_safe_turns}"
        )
        return report

    def to_dict(self) -> dict:
        r = self.build_report()
        return {
            "model": r.model,
            "context_window_size": r.context_window_size,
            "total_prompt_tokens": r.total_prompt_tokens,
            "total_completion_tokens": r.total_completion_tokens,
            "total_cost_usd": r.total_cost_usd,
            "avg_context_utilization_pct": r.avg_context_utilization_pct,
            "peak_context_utilization_pct": r.peak_context_utilization_pct,
            "efficiency_ratio": r.efficiency_ratio,
            "warning_turns": r.warning_turns,
            "critical_turns": r.critical_turns,
            "predicted_max_safe_turns": r.predicted_max_safe_turns,
            "snapshots": [
                {
                    "turn": s.turn,
                    "prompt_tokens": s.prompt_tokens,
                    "completion_tokens": s.completion_tokens,
                    "context_utilization_pct": s.context_utilization_pct,
                    "cost_usd": s.estimated_cost_usd,
                    "tokens_per_second": s.tokens_per_second,
                    "risk_level": s.risk_level,
                }
                for s in r.snapshots
            ],
        }
