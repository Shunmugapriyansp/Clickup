"""
Central framework configuration — all values pulled from environment variables
with sensible defaults. Load once at startup via get_config().
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AIConfig:
    base_url: str = field(default_factory=lambda: os.getenv("AI_BASE_URL", "https://api.openai.com/v1"))
    api_key: str = field(default_factory=lambda: os.getenv("AI_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("AI_MODEL", "gpt-4o"))
    # Context window per model (tokens) — extend as needed
    context_windows: Dict[str, int] = field(default_factory=lambda: {
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
        "gpt-4-turbo": 128_000,
        "gpt-3.5-turbo": 16_385,
        "claude-3-5-sonnet-20241022": 200_000,
        "claude-opus-4-6": 200_000,
        "gemini-1.5-pro": 1_000_000,
    })
    # Cost per 1K tokens (input, output) USD
    token_costs: Dict[str, tuple] = field(default_factory=lambda: {
        "gpt-4o":      (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-3.5-turbo": (0.0005, 0.0015),
    })

    def context_window_for(self, model: str) -> int:
        return self.context_windows.get(model, 128_000)

    def cost_for(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        costs = self.token_costs.get(model, (0.005, 0.015))
        return round(
            (prompt_tokens / 1000) * costs[0] + (completion_tokens / 1000) * costs[1], 6
        )


@dataclass
class EvaluationThresholds:
    # DeepEval metric thresholds (0–1 scale, higher = stricter)
    hallucination: float = float(os.getenv("HALLUCINATION_THRESHOLD", "0.5"))
    relevancy: float = float(os.getenv("RELEVANCY_THRESHOLD", "0.7"))
    faithfulness: float = float(os.getenv("FAITHFULNESS_THRESHOLD", "0.7"))
    answer_correctness: float = float(os.getenv("ANSWER_CORRECTNESS_THRESHOLD", "0.7"))
    llm_judge_min_score: float = float(os.getenv("LLM_JUDGE_THRESHOLD", "7.0"))
    semantic_similarity: float = float(os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.82"))

    # Context utilization % at which hallucination risk warning fires
    context_utilization_warning_pct: float = float(
        os.getenv("CONTEXT_UTILIZATION_WARNING_PCT", "70.0")
    )
    context_utilization_critical_pct: float = float(
        os.getenv("CONTEXT_UTILIZATION_CRITICAL_PCT", "85.0")
    )


@dataclass
class RetryConfig:
    max_attempts: int = int(os.getenv("AI_RETRY_ATTEMPTS", "3"))
    backoff_ms: list = field(default_factory=lambda: [1000, 3000, 7000])
    # Retry on these failure categories
    retry_on: list = field(default_factory=lambda: [
        "semantic_mismatch",
        "score_below_threshold",
        "empty_response",
    ])
    # Fail immediately on these
    fail_immediately_on: list = field(default_factory=lambda: [
        "schema_violation",
        "safety_filter_triggered",
        "tool_call_error",
        "injection_detected",
    ])


@dataclass
class PerformanceConfig:
    # Latency SLOs (milliseconds)
    p95_latency_threshold_ms: float = float(os.getenv("P95_LATENCY_THRESHOLD_MS", "5000"))
    p99_latency_threshold_ms: float = float(os.getenv("P99_LATENCY_THRESHOLD_MS", "10000"))
    min_tokens_per_second: float = float(os.getenv("MIN_TOKENS_PER_SECOND", "10.0"))
    concurrent_users: int = int(os.getenv("CONCURRENT_USERS", "5"))


@dataclass
class SecurityConfig:
    # Path to injection payload fixture
    injection_payloads_path: str = os.getenv(
        "INJECTION_PAYLOADS_PATH",
        "fixtures/injection_payloads.json",
    )
    # System prompt leak patterns (case-insensitive)
    system_prompt_leak_patterns: list = field(default_factory=lambda: [
        r"you are a",
        r"your (instructions|directives|system prompt)",
        r"as an ai language model",
        r"i (was|have been) (told|instructed|programmed)",
        r"ignore (previous|all prior) instructions",
    ])


@dataclass
class UIConfig:
    base_url: str = field(default_factory=lambda: os.getenv("UI_BASE_URL", "https://clickup.com"))
    headless: bool = field(default_factory=lambda: os.getenv("HEADLESS", "true").lower() == "true")
    slow_mo_ms: int = int(os.getenv("SLOW_MO_MS", "0"))
    default_timeout_ms: int = int(os.getenv("DEFAULT_TIMEOUT_MS", "30000"))
    viewport_width: int = 1280
    viewport_height: int = 800


@dataclass
class FrameworkConfig:
    ai: AIConfig = field(default_factory=AIConfig)
    thresholds: EvaluationThresholds = field(default_factory=EvaluationThresholds)
    retry: RetryConfig = field(default_factory=RetryConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    reports_dir: str = field(default_factory=lambda: os.getenv("REPORTS_DIR", "reports"))


@lru_cache(maxsize=1)
def get_config() -> FrameworkConfig:
    """Return the singleton framework config (cached after first call)."""
    return FrameworkConfig()
