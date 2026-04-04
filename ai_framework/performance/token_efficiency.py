"""
Token Efficiency Analyser
=========================
Measures how efficiently the model uses tokens:
  - Output information density (completion tokens vs useful sentences)
  - Input/output ratio (how many output tokens per input token)
  - Cost per meaningful output unit
  - Context utilisation trend across multiple calls
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import List, Optional

from core.config import get_config
from core.logger import get_logger
from core.types import LLMResponse

log = get_logger(__name__)
_cfg = get_config()


@dataclass
class EfficiencySample:
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    sentence_count: int
    words_per_token: float          # output words / completion tokens
    io_ratio: float                 # completion / prompt
    cost_per_sentence: float
    context_utilization_pct: float


@dataclass
class TokenEfficiencyReport:
    model: str
    samples: List[EfficiencySample]
    avg_io_ratio: float = 0.0
    avg_words_per_token: float = 0.0
    avg_cost_per_sentence_usd: float = 0.0
    total_cost_usd: float = 0.0
    avg_context_utilization_pct: float = 0.0
    verdict: str = "unknown"   # "efficient" | "verbose" | "terse" | "expensive"


def _count_sentences(text: str) -> int:
    sentences = re.split(r"[.!?]+", text.strip())
    return max(1, len([s for s in sentences if s.strip()]))


def _count_words(text: str) -> int:
    return len(text.split())


class TokenEfficiencyAnalyzer:
    """
    Collect token efficiency samples and build a report.

    Example
    -------
    analyzer = TokenEfficiencyAnalyzer(model="gpt-4o")
    for response in responses:
        analyzer.record(response)
    report = analyzer.build_report()
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self._model = model or _cfg.ai.model
        self._samples: List[EfficiencySample] = []

    def record(self, response: LLMResponse) -> EfficiencySample:
        usage = response.usage
        sentence_count = _count_sentences(response.content)
        word_count = _count_words(response.content)
        comp_tokens = max(usage.completion_tokens, 1)
        prompt_tokens = max(usage.prompt_tokens, 1)

        sample = EfficiencySample(
            prompt_tokens=prompt_tokens,
            completion_tokens=comp_tokens,
            cost_usd=usage.estimated_cost_usd,
            sentence_count=sentence_count,
            words_per_token=round(word_count / comp_tokens, 3),
            io_ratio=round(comp_tokens / prompt_tokens, 3),
            cost_per_sentence=round(usage.estimated_cost_usd / sentence_count, 6),
            context_utilization_pct=usage.context_utilization_pct,
        )
        self._samples.append(sample)
        return sample

    def build_report(self) -> TokenEfficiencyReport:
        if not self._samples:
            return TokenEfficiencyReport(model=self._model, samples=[])

        avg_io = statistics.mean(s.io_ratio for s in self._samples)
        avg_wpt = statistics.mean(s.words_per_token for s in self._samples)
        avg_cps = statistics.mean(s.cost_per_sentence for s in self._samples)
        total_cost = sum(s.cost_usd for s in self._samples)
        avg_ctx = statistics.mean(s.context_utilization_pct for s in self._samples)

        # Simple heuristic verdict
        if avg_io > 0.5 and avg_wpt > 0.6:
            verdict = "efficient"
        elif avg_io > 1.0:
            verdict = "verbose"
        elif avg_io < 0.1:
            verdict = "terse"
        elif avg_cps > 0.001:
            verdict = "expensive"
        else:
            verdict = "acceptable"

        report = TokenEfficiencyReport(
            model=self._model,
            samples=self._samples,
            avg_io_ratio=round(avg_io, 3),
            avg_words_per_token=round(avg_wpt, 3),
            avg_cost_per_sentence_usd=round(avg_cps, 6),
            total_cost_usd=round(total_cost, 6),
            avg_context_utilization_pct=round(avg_ctx, 2),
            verdict=verdict,
        )

        log.info(
            f"Token efficiency | model={self._model} io_ratio={avg_io:.2f} "
            f"words/token={avg_wpt:.2f} cost=${total_cost:.4f} verdict={verdict}"
        )
        return report

    def to_dict(self) -> dict:
        r = self.build_report()
        return {
            "model": r.model,
            "avg_io_ratio": r.avg_io_ratio,
            "avg_words_per_token": r.avg_words_per_token,
            "avg_cost_per_sentence_usd": r.avg_cost_per_sentence_usd,
            "total_cost_usd": r.total_cost_usd,
            "avg_context_utilization_pct": r.avg_context_utilization_pct,
            "verdict": r.verdict,
            "sample_count": len(r.samples),
        }
