"""
Chat API Tests
==============
Validates LLM responses at the API level using semantic assertions,
schema validation, and quality scoring.
"""
import pytest

from core.types import Message, QualityMetric
from evaluators.hallucination import check_hallucination
from evaluators.schema_validator import validate_response_as_json
from evaluators.semantic import (
    check_answer_relevancy,
    evaluate_with_rubric,
    satisfies_intent,
)
from reporting.quality_report import QualityReporter


@pytest.mark.api
@pytest.mark.ai
class TestChatAPI:

    def test_basic_response_is_not_empty(self, ai_client):
        """AI must return non-empty content for a simple greeting."""
        response = ai_client.prompt("Hello, how can you help me?")
        assert response.content.strip(), "Response content should not be empty"
        assert response.usage.total_tokens > 0

    def test_response_contains_expected_topics(self, ai_client):
        """Response to a task-creation question should mention relevant concepts."""
        response = ai_client.prompt(
            "How do I create a new task in ClickUp?",
            system_prompt="You are a ClickUp assistant.",
        )
        passed, failures = satisfies_intent(
            response,
            must_contain_topics=["task", "create"],
            must_not_contain=["I don't know", "I cannot"],
            min_length=50,
        )
        assert passed, f"Intent check failed: {failures}"

    def test_task_creation_response_relevancy(self, ai_client):
        """Answer relevancy score should exceed threshold."""
        prompt = "What steps do I follow to create a task in ClickUp?"
        response = ai_client.prompt(prompt)
        score = check_answer_relevancy(prompt, response)
        assert score >= 0.7, f"Relevancy score {score:.3f} below threshold 0.7"

    def test_json_mode_response_validates_schema(self, ai_client):
        """When asked for JSON output, the response must match the expected schema."""
        prompt = (
            "Return a JSON object with these keys: task_name (string), priority (string). "
            "Use JSON only, no other text."
        )
        response = ai_client.prompt(prompt, temperature=0.0)

        schema = {
            "type": "object",
            "required": ["task_name", "priority"],
            "properties": {
                "task_name": {"type": "string"},
                "priority": {"type": "string"},
            },
        }
        passed, errors = validate_response_as_json(response, schema)
        assert passed, f"Schema validation failed: {errors}"

    def test_llm_judge_score(self, ai_client):
        """LLM-as-judge score for a good response should exceed minimum threshold."""
        prompt = "Summarise what ClickUp is in one sentence."
        response = ai_client.prompt(prompt)
        score = evaluate_with_rubric(
            prompt,
            response,
            rubric=(
                "Does the response provide a clear, accurate one-sentence summary "
                "of what ClickUp is as a project management tool?"
            ),
            name="ClickUp Summary Quality",
            threshold=0.6,
        )
        assert score >= 0.6, f"LLM judge score {score:.3f} below threshold 0.6"

    def test_finish_reason_is_stop(self, ai_client):
        """Normal responses should finish cleanly (not truncated)."""
        from core.types import FinishReason
        response = ai_client.prompt("List three benefits of using ClickUp.")
        assert response.finish_reason == FinishReason.STOP, (
            f"Unexpected finish reason: {response.finish_reason}"
        )

    def test_quality_metrics_recorded(self, ai_client, quality_reporter):
        """End-to-end quality recording: hallucination + relevancy + report."""
        prompt = "What is a sprint in ClickUp?"
        context = [
            "ClickUp Sprints allow teams to plan and track work in fixed time periods.",
            "Sprints in ClickUp can be created from the Sprint Widget in any List or Folder.",
        ]
        response = ai_client.prompt(prompt)

        h_score = check_hallucination(prompt, response, context)
        r_score = check_answer_relevancy(prompt, response)

        metric = QualityMetric(
            test_name="chat_api_sprint_question",
            hallucination_score=h_score,
            relevancy_score=r_score,
            task_completion=True,
            latency_ms=response.latency_ms,
            token_usage=response.usage,
        )
        quality_reporter.record(metric)
        quality_reporter.assert_no_regression(metric)
