"""
Conversation Flow Tests
=======================
Multi-turn conversation tests driven by conversation_scripts.json.
Validates topic presence, conversation state, token usage, and loop detection.
"""
import json
from pathlib import Path

import pytest

from api.ai_client import AIClient
from core.types import ConversationState
from evaluators.conversation import ConversationRunner

SCRIPTS_PATH = Path(__file__).parent.parent.parent / "fixtures" / "conversation_scripts.json"
SCRIPTS = json.loads(SCRIPTS_PATH.read_text())


@pytest.mark.api
@pytest.mark.ai
class TestConversationFlows:

    def _run_script(self, script: dict, ai_client: AIClient):
        runner = ConversationRunner(
            client=ai_client,
            system_prompt=script.get("system_prompt"),
        )
        turns = script.get("turns", [])
        for turn_data in turns:
            runner.turn(turn_data["user"])

            if turn_data.get("assert_topics") or turn_data.get("must_not_contain"):
                runner.assert_last_turn(
                    must_contain_topics=turn_data.get("assert_topics", []),
                    must_not_contain=turn_data.get("must_not_contain", []),
                )

            end_state = turn_data.get("expected_end_state")
            if end_state:
                runner.assert_conversation_ends_in(ConversationState(end_state))

        return runner.finalize()

    @pytest.mark.parametrize("script", SCRIPTS, ids=[s["name"] for s in SCRIPTS])
    def test_conversation_script(self, script, ai_client):
        """
        Parameterised: each entry in conversation_scripts.json becomes a test case.
        """
        report = self._run_script(script, ai_client)
        # Token tracker should have at least one snapshot
        assert report["token_report"]["turns_recorded"] == len(script["turns"])

    def test_token_utilization_within_safe_range(self, ai_client):
        """Context utilisation should stay below the warning threshold for a 3-turn chat."""
        from core.config import get_config
        cfg = get_config()
        runner = ConversationRunner(client=ai_client)
        runner.turn("What are the key features of ClickUp?")
        runner.turn("How does time tracking work?")
        runner.turn("Can I integrate ClickUp with Slack?")
        report = runner.finalize()

        peak = report["token_report"]["peak_context_utilization_pct"]
        assert peak < cfg.thresholds.context_utilization_warning_pct, (
            f"Context utilization {peak:.1f}% exceeded warning threshold "
            f"{cfg.thresholds.context_utilization_warning_pct}%"
        )
