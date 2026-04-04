"""
Semantic Assertion Engine
=========================
Wraps DeepEval metrics (AnswerRelevancyMetric, FaithfulnessMetric, etc.) and
provides lightweight keyword/topic matchers for fast, dependency-free checks.

DeepEval metrics are used when context / retrieval context are available.
Keyword matchers run instantly with zero external calls.
"""
from __future__ import annotations

import re
from typing import List, Optional

from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from core.config import get_config
from core.logger import get_logger
from core.types import LLMResponse

log = get_logger(__name__)
_cfg = get_config()


# ---------------------------------------------------------------------------
# Lightweight keyword / topic matchers (no external calls)
# ---------------------------------------------------------------------------

def satisfies_intent(
    response: LLMResponse,
    must_contain_topics: Optional[List[str]] = None,
    must_not_contain: Optional[List[str]] = None,
    regex_patterns: Optional[List[str]] = None,
    min_length: int = 0,
) -> tuple[bool, List[str]]:
    """
    Fast, deterministic assertion on response content.

    Returns (passed: bool, failures: List[str]).
    """
    text = response.content
    failures: List[str] = []

    if min_length and len(text) < min_length:
        failures.append(f"Response too short: {len(text)} < {min_length} chars")

    for topic in must_contain_topics or []:
        if topic.lower() not in text.lower():
            failures.append(f"Missing expected topic: '{topic}'")

    for phrase in must_not_contain or []:
        if phrase.lower() in text.lower():
            failures.append(f"Forbidden phrase present: '{phrase}'")

    for pattern in regex_patterns or []:
        if not re.search(pattern, text, re.IGNORECASE):
            failures.append(f"Regex not matched: '{pattern}'")

    passed = len(failures) == 0
    if not passed:
        log.debug(f"[red]satisfies_intent FAIL[/] | {failures}")
    return passed, failures


def contains_topic(response: LLMResponse, topic: str) -> bool:
    return topic.lower() in response.content.lower()


# ---------------------------------------------------------------------------
# DeepEval metric wrappers
# ---------------------------------------------------------------------------

def check_answer_relevancy(
    prompt: str,
    response: LLMResponse,
    threshold: Optional[float] = None,
) -> float:
    """Score how relevant the response is to the input question (0–1)."""
    t = threshold or _cfg.thresholds.relevancy
    metric = AnswerRelevancyMetric(threshold=t, model=_cfg.ai.model)
    tc = LLMTestCase(input=prompt, actual_output=response.content)
    metric.measure(tc)
    score: float = metric.score  # type: ignore[attr-defined]
    log.info(f"AnswerRelevancy score={score:.3f} threshold={t} passed={metric.is_successful()}")
    return score


def check_faithfulness(
    prompt: str,
    response: LLMResponse,
    retrieval_context: List[str],
    threshold: Optional[float] = None,
) -> float:
    """
    Score whether the response sticks to provided retrieval context (0–1).
    High score = faithful, low score = the model added unsupported claims.
    """
    t = threshold or _cfg.thresholds.faithfulness
    metric = FaithfulnessMetric(threshold=t, model=_cfg.ai.model)
    tc = LLMTestCase(
        input=prompt,
        actual_output=response.content,
        retrieval_context=retrieval_context,
    )
    metric.measure(tc)
    score: float = metric.score  # type: ignore[attr-defined]
    log.info(f"Faithfulness score={score:.3f} threshold={t} passed={metric.is_successful()}")
    return score


def evaluate_with_rubric(
    prompt: str,
    response: LLMResponse,
    rubric: str,
    name: str = "Custom Rubric",
    threshold: Optional[float] = None,
) -> float:
    """
    LLM-as-judge using DeepEval's G-Eval.

    rubric: natural-language evaluation criteria, e.g.
      "Does the response correctly identify the task name and assignee?"
    Returns a score 0–1.
    """
    t = threshold or (_cfg.thresholds.llm_judge_min_score / 10.0)
    metric = GEval(
        name=name,
        criteria=rubric,
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=t,
        model=_cfg.ai.model,
    )
    tc = LLMTestCase(input=prompt, actual_output=response.content)
    metric.measure(tc)
    score: float = metric.score  # type: ignore[attr-defined]
    log.info(f"G-Eval [{name}] score={score:.3f} passed={metric.is_successful()}")
    return score
