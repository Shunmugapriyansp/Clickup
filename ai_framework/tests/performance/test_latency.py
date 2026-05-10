"""
Latency & Throughput Tests
===========================
Measures P50/P95/P99 latency, tokens/sec, and streaming TTFB.
Asserts against SLO thresholds defined in config / baselines.
"""
import pytest

from api.ai_client import AIClient
from core.types import Message
from performance.benchmarks import get_baseline
from performance.latency_tracker import LatencyTracker
from reporting.performance_report import save_performance_report


@pytest.mark.performance
class TestLatency:

    def test_single_request_latency(self, ai_client: AIClient):
        """Single chat request must respond within the P95 SLO."""
        tracker = LatencyTracker("single_request")
        with tracker.measure() as t:
            response = ai_client.prompt("What is ClickUp?")
            t.prompt_tokens = response.usage.prompt_tokens
            t.completion_tokens = response.usage.completion_tokens
            t.tokens_per_second = response.tokens_per_second

        tracker.assert_slo()

    def test_multi_sample_latency_percentiles(self, ai_client: AIClient):
        """Run 5 requests and assert P95 meets SLO."""
        prompts = [
            "List 3 ClickUp features.",
            "What is a task dependency?",
            "How do I set up a workspace?",
            "Explain ClickUp goals.",
            "What integrations does ClickUp support?",
        ]
        tracker = LatencyTracker("multi_sample", baseline=get_baseline("chat_api_gpt4o"))
        for prompt in prompts:
            with tracker.measure() as t:
                response = ai_client.prompt(prompt)
                t.prompt_tokens = response.usage.prompt_tokens
                t.completion_tokens = response.usage.completion_tokens
                t.tokens_per_second = response.tokens_per_second

        save_performance_report(tracker.to_dict())
        tracker.assert_slo()

    def test_streaming_ttfb(self, ai_client: AIClient):
        """Streaming time-to-first-byte must be < 2 seconds."""
        response = ai_client.chat_stream(
            messages=[Message(role="user", content="Briefly describe ClickUp.")]
        )
        assert response.ttfb_ms < 2000, (
            f"Streaming TTFB {response.ttfb_ms:.0f}ms exceeded 2000ms threshold."
        )
        assert response.content.strip(), "Streaming response content should not be empty."

    def test_tokens_per_second_meets_minimum(self, ai_client: AIClient):
        """Generation speed must meet minimum tokens/second threshold."""
        from core.config import get_config
        cfg = get_config()
        response = ai_client.prompt(
            "Write a detailed 5-step guide to creating a project in ClickUp."
        )
        assert response.tokens_per_second >= cfg.performance.min_tokens_per_second, (
            f"Tokens/sec {response.tokens_per_second:.1f} below minimum "
            f"{cfg.performance.min_tokens_per_second}"
        )
