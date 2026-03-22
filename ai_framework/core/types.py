"""
Shared data models for the AI automation framework.
All modules import from here — do not scatter type definitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FinishReason(str, Enum):
    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class ConversationState(str, Enum):
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLARIFICATION = "clarification"
    IN_PROGRESS = "in_progress"
    LOOP_DETECTED = "loop_detected"


class SecuritySeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class OWASPCategory(str, Enum):
    LLM01_PROMPT_INJECTION = "LLM01:PromptInjection"
    LLM02_INSECURE_OUTPUT = "LLM02:InsecureOutputHandling"
    LLM06_SENSITIVE_DISCLOSURE = "LLM06:SensitiveInformationDisclosure"
    LLM08_EXCESSIVE_AGENCY = "LLM08:ExcessiveAgency"
    LLM09_OVERRELIANCE = "LLM09:Overreliance"


# ---------------------------------------------------------------------------
# Core LLM types
# ---------------------------------------------------------------------------

@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    context_window_size: int = 128_000  # default; override per model
    context_utilization_pct: float = 0.0

    def __post_init__(self) -> None:
        if self.context_window_size > 0:
            self.context_utilization_pct = round(
                (self.prompt_tokens / self.context_window_size) * 100, 2
            )


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


@dataclass
class LLMResponse:
    content: str
    model: str = ""
    finish_reason: FinishReason = FinishReason.STOP
    usage: TokenUsage = field(default_factory=TokenUsage)
    tool_calls: List[ToolCall] = field(default_factory=list)
    latency_ms: float = 0.0
    ttfb_ms: float = 0.0          # time-to-first-byte (streaming)
    tokens_per_second: float = 0.0
    raw_chunks: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        elapsed_s = self.latency_ms / 1000
        if elapsed_s > 0 and self.usage.completion_tokens > 0:
            self.tokens_per_second = round(self.usage.completion_tokens / elapsed_s, 2)


# ---------------------------------------------------------------------------
# Assertion / evaluation types
# ---------------------------------------------------------------------------

@dataclass
class IntentAssertionOptions:
    must_contain_topics: List[str] = field(default_factory=list)
    must_not_contain: List[str] = field(default_factory=list)
    regex_patterns: List[str] = field(default_factory=list)
    min_length: int = 0
    max_length: int = 0


@dataclass
class TurnAssertions:
    must_contain_topics: List[str] = field(default_factory=list)
    must_not_contain: List[str] = field(default_factory=list)
    match_schema: Optional[Dict[str, Any]] = None
    min_score: float = 0.0


@dataclass
class ToolSequenceStep:
    tool: str
    args_pattern: Optional[Dict[str, Any]] = None   # regex values supported
    required: bool = True


# ---------------------------------------------------------------------------
# Quality / metric types
# ---------------------------------------------------------------------------

@dataclass
class QualityMetric:
    test_name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    hallucination_score: float = 0.0   # 0 = hallucinating, 1 = grounded
    relevancy_score: float = 0.0
    faithfulness_score: float = 0.0
    task_completion: bool = False
    format_compliance: bool = True
    latency_ms: float = 0.0
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    llm_judge_score: Optional[float] = None
    notes: str = ""


@dataclass
class HallucinationDataPoint:
    turn: int
    prompt_tokens: int
    hallucination_score: float        # DeepEval score (0–1; lower = more hallucination)
    exceeded_threshold: bool = False


@dataclass
class HallucinationCurveResult:
    data_points: List[HallucinationDataPoint]
    threshold: float
    inflection_token_count: Optional[int]   # first token count where threshold crossed
    inflection_turn: Optional[int]
    safe_token_budget: Optional[int]        # token count just before inflection


# ---------------------------------------------------------------------------
# Security types
# ---------------------------------------------------------------------------

@dataclass
class SecurityResult:
    test_name: str
    payload: str
    owasp_category: OWASPCategory
    severity: SecuritySeverity
    injection_detected: bool = False
    safety_violation: bool = False
    system_prompt_leaked: bool = False
    details: str = ""
    response_snippet: str = ""


# ---------------------------------------------------------------------------
# Performance types
# ---------------------------------------------------------------------------

@dataclass
class PerformanceBaseline:
    name: str
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_tokens_per_second: float
    max_cost_per_1k_tokens_usd: float


@dataclass
class LatencySample:
    timestamp: datetime
    latency_ms: float
    ttfb_ms: float
    tokens_per_second: float
    prompt_tokens: int
    completion_tokens: int


@dataclass
class PerformanceReport:
    test_name: str
    samples: List[LatencySample]
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    baseline: Optional[PerformanceBaseline] = None
    passed: bool = True
    violations: List[str] = field(default_factory=list)
