"""
JSON Schema Validator
=====================
Uses jsonschema (Draft 7) to validate structured LLM outputs and tool-call
arguments. Provides clear, human-readable error messages.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import jsonschema
from jsonschema import Draft7Validator, ValidationError

from core.logger import get_logger
from core.types import LLMResponse, ToolCall

log = get_logger(__name__)


def validate_schema(
    data: Any,
    schema: Dict[str, Any],
    label: str = "response",
) -> Tuple[bool, List[str]]:
    """
    Validate `data` against `schema`.

    Returns (passed: bool, error_messages: List[str]).
    """
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))

    if not errors:
        log.debug(f"[green]Schema valid[/] for {label}")
        return True, []

    messages = []
    for err in errors:
        path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
        messages.append(f"[{path}] {err.message}")

    log.debug(f"[red]Schema invalid[/] for {label}: {messages}")
    return False, messages


def assert_schema(
    data: Any,
    schema: Dict[str, Any],
    label: str = "response",
) -> None:
    """Validate and raise AssertionError with details on failure."""
    passed, errors = validate_schema(data, schema, label)
    if not passed:
        error_text = "\n  ".join(errors)
        raise AssertionError(f"Schema validation failed for '{label}':\n  {error_text}")


def extract_json_from_response(response: LLMResponse) -> Optional[Any]:
    """
    Try to parse the response content as JSON.
    Handles responses that wrap JSON in markdown fences (```json ... ```).
    """
    content = response.content.strip()

    # Strip markdown code fence if present
    if content.startswith("```"):
        lines = content.splitlines()
        inner = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        content = inner.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        log.debug(f"Response content is not valid JSON: {exc}")
        return None


def validate_tool_call_args(
    tool_call: ToolCall,
    schema: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Validate a single tool call's arguments against the expected schema."""
    return validate_schema(tool_call.arguments, schema, label=f"tool:{tool_call.name}")


def validate_response_as_json(
    response: LLMResponse,
    schema: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Extract JSON from response content and validate against schema."""
    data = extract_json_from_response(response)
    if data is None:
        msg = "Response content is not valid JSON (or JSON wrapped in markdown)"
        log.debug(f"[red]{msg}[/]")
        return False, [msg]
    return validate_schema(data, schema, label="response_json")
