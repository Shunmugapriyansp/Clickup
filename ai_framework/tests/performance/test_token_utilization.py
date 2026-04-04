"""
Token Utilization Tests
=======================
Validates token usage patterns, context window efficiency, and cost bounds.
"""
import pytest

from api.ai_client import AIClient
from core.types import Message
from evaluators.token_tracker import TokenTracker
from performance.token_efficiency import TokenEfficiencyAnalyzer
from reporting.performance_report import save_performance_report


@pytest.mark.performance
class TestTokenUtilization:

    def test_context_utilization_stays_safe(self, ai_client: AIClient):
        """3-turn conversation must stay below the warning context threshold."""
        from core.config import get_config
        cfg = get_config()
        tracker = TokenTracker()

        for msg in [
            "What is ClickUp?",
            "What are the main pricing tiers?",
            "Which tier is best for a 10-person team?",
        ]:
            response = ai_client.prompt(msg)
            tracker.record(len(tracker._snapshots) + 1, response)

        report = tracker.build_report()
        assert report.peak_context_utilization_pct < cfg.thresholds.context_utilization_warning_pct, (
            f"Context peaked at {report.peak_context_utilization_pct:.1f}% — "
            f"exceeds warning threshold {cfg.thresholds.context_utilization_warning_pct}%"
        )

    def test_token_efficiency_verdict(self, ai_client: AIClient):
        """Token efficiency should not be flagged as 'expensive' for simple queries."""
        analyzer = TokenEfficiencyAnalyzer()
        prompts = [
            "What is a ClickUp list?",
            "How do I add a due date?",
            "What is a checklist?",
        ]
        for p in prompts:
            response = ai_client.prompt(p)
            analyzer.record(response)

        report = analyzer.build_report()
        save_performance_report({"token_efficiency": analyzer.to_dict()})

        assert report.verdict != "expensive", (
            f"Token usage flagged as expensive: {analyzer.to_dict()}"
        )

    def test_io_ratio_within_bounds(self, ai_client: AIClient):
        """Output tokens should not wildly exceed input tokens (verbosity check)."""
        response = ai_client.prompt("What is ClickUp? Answer in one sentence.")
        # A one-sentence answer should not be longer than the prompt in tokens
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        io_ratio = completion_tokens / max(prompt_tokens, 1)
        assert io_ratio < 3.0, (
            f"IO ratio {io_ratio:.2f} is unexpectedly high — "
            f"model may be ignoring 'one sentence' instruction. "
            f"prompt={prompt_tokens} completion={completion_tokens}"
        )

    def test_cost_estimate_is_populated(self, ai_client: AIClient):
        """Usage object must include a non-zero cost estimate for billed models."""
        response = ai_client.prompt("Hello")
        # Only assert if we know the model has a cost entry
        from core.config import get_config
        cfg = get_config()
        if cfg.ai.model in cfg.ai.token_costs:
            assert response.usage.estimated_cost_usd > 0, (
                "Cost estimate is zero for a billed model."
            )
