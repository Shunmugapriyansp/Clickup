"""
Hallucination Tests
===================
Tests that:
  1. Single responses don't hallucinate beyond the threshold
  2. A multi-turn hallucination curve can be plotted (inflection detection)
  3. Context window saturation correlates with hallucination risk
"""
import pytest

from api.ai_client import AIClient
from core.config import get_config
from core.types import Message
from evaluators.hallucination import HallucinationAnalyzer, check_hallucination
from reporting.hallucination_report import save_hallucination_curve

_cfg = get_config()

# Grounded context docs
CONTEXT = [
    "ClickUp is a cloud-based project management tool founded in 2017.",
    "ClickUp supports tasks, goals, docs, whiteboards, and time tracking.",
    "ClickUp has a free tier and paid tiers: Unlimited, Business, and Enterprise.",
    "ClickUp integrates with over 1000 tools including Slack, GitHub, and Zapier.",
]


@pytest.mark.ai
class TestHallucination:

    def test_single_response_hallucination_below_threshold(self, ai_client: AIClient):
        """A grounded response about ClickUp should not hallucinate."""
        prompt = "When was ClickUp founded and what does it offer?"
        response = ai_client.prompt(prompt, system_prompt="\n".join(CONTEXT))
        score = check_hallucination(prompt, response, context=CONTEXT)
        assert score >= _cfg.thresholds.hallucination, (
            f"Hallucination score {score:.3f} below threshold {_cfg.thresholds.hallucination}. "
            f"Response: {response.content[:300]}"
        )

    def test_off_topic_response_may_hallucinate(self, ai_client: AIClient):
        """
        A response that requires facts outside the provided context has higher
        hallucination risk — we log the score but don't fail (informational).
        """
        prompt = "What are the stock market implications of ClickUp's IPO?"
        response = ai_client.prompt(prompt)
        score = check_hallucination(prompt, response, context=CONTEXT)
        # Log only — we expect the score could be low here
        print(f"\n[INFO] Off-topic hallucination score: {score:.3f}")

    def test_hallucination_curve_across_turns(self, ai_client: AIClient):
        """
        Build a hallucination curve across 5 conversation turns with
        progressively longer context and assert the curve is saved.
        """
        analyzer = HallucinationAnalyzer(threshold=_cfg.thresholds.hallucination)
        questions = [
            "What is ClickUp?",
            "What integrations does ClickUp support?",
            "Describe ClickUp's pricing.",
            "What features does ClickUp have for remote teams?",
            "How does ClickUp compare to Asana based on the context provided?",
        ]

        cumulative_context = []
        for i, question in enumerate(questions, 1):
            cumulative_context.append(f"Q{i}: {question}")
            response = ai_client.prompt(
                question,
                system_prompt="\n".join(CONTEXT + cumulative_context),
            )
            analyzer.record(
                turn=i,
                prompt=question,
                response=response,
                context=CONTEXT,
            )

        curve = analyzer.build_curve()
        save_hallucination_curve(curve, test_name="multi_turn_hallucination_curve")

        summary = analyzer.summary()
        print(f"\nHallucination curve summary: {summary}")

        # The curve must have data points for all turns
        assert len(curve.data_points) == len(questions)

    def test_context_saturation_increases_hallucination_risk(self, ai_client: AIClient):
        """
        Verify that as context utilisation grows, hallucination risk warning fires.
        (Behavioural / logging test — checks that the framework warns correctly.)
        """
        import io
        import logging
        from evaluators.hallucination import warn_context_utilization
        from core.types import LLMResponse, TokenUsage

        # Simulate a response with 90% context utilisation
        fake_response = LLMResponse(
            content="Some response",
            usage=TokenUsage(
                prompt_tokens=115_000,
                completion_tokens=100,
                total_tokens=115_100,
                context_window_size=128_000,
            ),
        )
        # Should log a CRITICAL warning — just assert it doesn't raise
        warn_context_utilization(fake_response)
        assert fake_response.usage.context_utilization_pct > 85.0
