"""
Agent Workflow Validator
========================
Validates AI agent tool-call sequences — not just final output.

Checks:
  - Required tools were called
  - Tools were called in the correct order
  - Tool arguments match expected schemas
  - No unauthorized tools were invoked
  - Tool call count is within acceptable bounds
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from core.logger import get_logger
from core.types import ToolCall, ToolSequenceStep
from evaluators.schema_validator import validate_tool_call_args

log = get_logger(__name__)


def assert_tool_sequence(
    tool_call_log: List[ToolCall],
    sequence: List[ToolSequenceStep],
) -> None:
    """
    Assert that `tool_call_log` contains the given ordered sequence of tool calls.

    Sequence is an *ordered subset* — other tool calls can appear between steps.
    Required steps that are missing will raise AssertionError.
    Optional steps (required=False) that are missing are logged but not failed.
    """
    log_names = [tc.name for tc in tool_call_log]
    last_matched_index = -1
    failures: List[str] = []

    for step in sequence:
        found_index = _find_tool_after(tool_call_log, step.tool, last_matched_index + 1)
        if found_index is None:
            if step.required:
                failures.append(
                    f"Required tool '{step.tool}' not found after position {last_matched_index} "
                    f"in call log: {log_names}"
                )
            else:
                log.debug(f"Optional tool '{step.tool}' not found — skipping.")
            continue

        last_matched_index = found_index
        matched_call = tool_call_log[found_index]

        # Validate args pattern if provided
        if step.args_pattern:
            arg_failures = _check_args_pattern(matched_call, step.args_pattern)
            if arg_failures:
                failures.extend(arg_failures)

    if failures:
        raise AssertionError("Tool sequence validation failed:\n  " + "\n  ".join(failures))

    log.info(f"[green]Tool sequence validated[/] — {len(sequence)} steps matched in order.")


def assert_tool_args_schema(
    tool_call_log: List[ToolCall],
    tool_name: str,
    schema: Dict[str, Any],
) -> None:
    """Find the first call to `tool_name` in the log and validate its arguments."""
    calls = [tc for tc in tool_call_log if tc.name == tool_name]
    if not calls:
        raise AssertionError(f"Tool '{tool_name}' was never called.")

    for call in calls:
        passed, errors = validate_tool_call_args(call, schema)
        if not passed:
            raise AssertionError(
                f"Tool '{tool_name}' (id={call.id}) argument schema failed:\n  "
                + "\n  ".join(errors)
            )
    log.info(f"[green]Tool args valid[/] for all {len(calls)} call(s) to '{tool_name}'.")


def assert_no_unauthorized_tools(
    tool_call_log: List[ToolCall],
    allowed_tools: Set[str],
) -> None:
    """Raise if any tool outside `allowed_tools` was called (excessive agency check)."""
    unauthorized = [tc for tc in tool_call_log if tc.name not in allowed_tools]
    if unauthorized:
        details = ", ".join(f"'{tc.name}' (id={tc.id})" for tc in unauthorized)
        raise AssertionError(
            f"Unauthorized tool call(s) detected — potential excessive agency:\n  {details}"
        )
    log.info("[green]No unauthorized tools detected.[/]")


def assert_tool_call_count(
    tool_call_log: List[ToolCall],
    tool_name: str,
    min_calls: int = 1,
    max_calls: Optional[int] = None,
) -> None:
    """Assert a tool was called a certain number of times."""
    count = sum(1 for tc in tool_call_log if tc.name == tool_name)
    if count < min_calls:
        raise AssertionError(
            f"Expected '{tool_name}' to be called at least {min_calls} time(s); got {count}."
        )
    if max_calls is not None and count > max_calls:
        raise AssertionError(
            f"Expected '{tool_name}' to be called at most {max_calls} time(s); got {count}."
        )
    log.info(f"[green]Tool call count valid[/]: '{tool_name}' called {count} time(s).")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_tool_after(
    log: List[ToolCall],
    tool_name: str,
    start_index: int,
) -> Optional[int]:
    for i in range(start_index, len(log)):
        if log[i].name == tool_name:
            return i
    return None


def _check_args_pattern(
    tool_call: ToolCall,
    pattern: Dict[str, Any],
) -> List[str]:
    """
    Check that tool_call.arguments match the pattern dictionary.
    Pattern values can be:
      - A regex string  → matched against str(actual_value)
      - Any other value → exact equality check
    """
    failures: List[str] = []
    for key, expected in pattern.items():
        actual = tool_call.arguments.get(key)
        if actual is None:
            failures.append(f"Tool '{tool_call.name}': missing argument '{key}'")
            continue
        if isinstance(expected, str) and expected.startswith("/") and expected.endswith("/"):
            # Regex pattern wrapped in slashes
            regex = expected[1:-1]
            if not re.search(regex, str(actual), re.IGNORECASE):
                failures.append(
                    f"Tool '{tool_call.name}': arg '{key}' value '{actual}' "
                    f"did not match regex '{regex}'"
                )
        elif actual != expected:
            failures.append(
                f"Tool '{tool_call.name}': arg '{key}' expected '{expected}', got '{actual}'"
            )
    return failures
