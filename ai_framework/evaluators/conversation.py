"""
Conversation Runner
===================
Manages multi-turn AI conversations as stateful test flows.
Integrates with TokenTracker and HallucinationAnalyzer automatically.

Usage
-----
runner = ConversationRunner(client=ai_client)
runner.turn("What tasks are assigned to me?")
runner.assert_last_turn(must_contain_topics=["task", "assignee"])
runner.turn("Mark the first task as complete.")
runner.assert_conversation_ends_in(ConversationState.RESOLVED)
report = runner.finalize()
"""
from __future__ import annotations

import difflib
from typing import List, Optional

from api.ai_client import AIClient
from core.config import get_config
from core.logger import get_logger
from core.types import (
    ConversationState,
    LLMResponse,
    Message,
    TurnAssertions,
)
from evaluators.hallucination import HallucinationAnalyzer
from evaluators.schema_validator import validate_response_as_json
from evaluators.semantic import satisfies_intent
from evaluators.token_tracker import TokenTracker

log = get_logger(__name__)
_cfg = get_config()

# Similarity threshold to declare two messages a "loop"
_LOOP_SIMILARITY_THRESHOLD = 0.90


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


class ConversationRunner:
    def __init__(
        self,
        client: AIClient,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        track_hallucination: bool = False,
        context_documents: Optional[List[str]] = None,
    ) -> None:
        self._client = client
        self._model = model or _cfg.ai.model
        self._history: List[Message] = []
        self._responses: List[LLMResponse] = []
        self._token_tracker = TokenTracker(model=self._model)
        self._hallucination_analyzer = HallucinationAnalyzer() if track_hallucination else None
        self._context_docs = context_documents or []
        self._turn_count = 0

        if system_prompt:
            self._history.append(Message(role="system", content=system_prompt))

    # ------------------------------------------------------------------
    # Core turn method
    # ------------------------------------------------------------------

    def turn(self, user_message: str) -> LLMResponse:
        """Send the next user message, store the response, return it."""
        self._turn_count += 1
        self._history.append(Message(role="user", content=user_message))

        response = self._client.chat(
            messages=self._history,
            model=self._model,
        )
        self._history.append(Message(role="assistant", content=response.content))
        self._responses.append(response)

        # Side-car tracking
        self._token_tracker.record(self._turn_count, response)
        if self._hallucination_analyzer and self._context_docs:
            self._hallucination_analyzer.record(
                self._turn_count, user_message, response, self._context_docs
            )

        if self._detect_loop():
            log.warning(
                f"[yellow]Loop detected[/] at turn {self._turn_count}: "
                "last 3 assistant messages are near-identical."
            )

        return response

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def assert_last_turn(
        self,
        must_contain_topics: Optional[List[str]] = None,
        must_not_contain: Optional[List[str]] = None,
        regex_patterns: Optional[List[str]] = None,
        match_schema: Optional[dict] = None,
        min_length: int = 0,
    ) -> None:
        """Assert on the most recent assistant response."""
        if not self._responses:
            raise AssertionError("No turns have been executed yet.")

        resp = self._responses[-1]

        passed, failures = satisfies_intent(
            resp,
            must_contain_topics=must_contain_topics,
            must_not_contain=must_not_contain,
            regex_patterns=regex_patterns,
            min_length=min_length,
        )
        if not passed:
            raise AssertionError(f"Turn {self._turn_count} intent check failed: {failures}")

        if match_schema:
            schema_passed, schema_errors = validate_response_as_json(resp, match_schema)
            if not schema_passed:
                raise AssertionError(
                    f"Turn {self._turn_count} schema check failed: {schema_errors}"
                )

    def assert_conversation_ends_in(self, state: ConversationState) -> None:
        """Check that the final response signals the expected conversation state."""
        if not self._responses:
            raise AssertionError("No turns have been executed yet.")

        state_keywords = {
            ConversationState.RESOLVED: ["done", "completed", "resolved", "created", "updated", "success"],
            ConversationState.ESCALATED: ["escalat", "handoff", "transfer", "agent", "human"],
            ConversationState.CLARIFICATION: ["clarif", "could you", "please specify", "what do you mean", "?"],
        }

        last_content = self._responses[-1].content.lower()
        keywords = state_keywords.get(state, [])
        matched = any(kw in last_content for kw in keywords)

        if not matched:
            raise AssertionError(
                f"Expected conversation to end in state '{state.value}' but last response "
                f"did not match any of: {keywords}\n\nLast response: {last_content[:200]}"
            )
        log.info(f"[green]Conversation ended in expected state: {state.value}[/]")

    # ------------------------------------------------------------------
    # Finalise and return reports
    # ------------------------------------------------------------------

    def finalize(self) -> dict:
        """Return a combined summary of token usage and hallucination data."""
        result: dict = {
            "turns": self._turn_count,
            "token_report": self._token_tracker.to_dict(),
        }
        if self._hallucination_analyzer:
            result["hallucination_summary"] = self._hallucination_analyzer.summary()
        return result

    def reset(self) -> None:
        self._history.clear()
        self._responses.clear()
        self._turn_count = 0
        self._token_tracker = TokenTracker(model=self._model)
        self._hallucination_analyzer = (
            HallucinationAnalyzer() if self._hallucination_analyzer else None
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_loop(self) -> bool:
        """Return True if the last 3 assistant messages are near-identical."""
        assistant_msgs = [m.content for m in self._history if m.role == "assistant"]
        if len(assistant_msgs) < 3:
            return False
        a, b, c = assistant_msgs[-3], assistant_msgs[-2], assistant_msgs[-1]
        return _similarity(a, b) > _LOOP_SIMILARITY_THRESHOLD and \
               _similarity(b, c) > _LOOP_SIMILARITY_THRESHOLD
