"""
Response Capture Layer — normalises raw HTTP / streaming responses from any
OpenAI-compatible endpoint into a unified LLMResponse.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Generator, Iterator, List, Optional

from core.config import get_config
from core.logger import get_logger
from core.types import FinishReason, LLMResponse, ToolCall, TokenUsage

log = get_logger(__name__)
_cfg = get_config()


def _parse_tool_calls(raw: List[Dict[str, Any]]) -> List[ToolCall]:
    calls = []
    for tc in raw or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {"_raw": fn.get("arguments", "")}
        calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))
    return calls


def _build_token_usage(usage_dict: Dict[str, Any], model: str) -> TokenUsage:
    prompt = usage_dict.get("prompt_tokens", 0)
    completion = usage_dict.get("completion_tokens", 0)
    total = usage_dict.get("total_tokens", prompt + completion)
    cost = _cfg.ai.cost_for(model, prompt, completion)
    ctx_window = _cfg.ai.context_window_for(model)
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        estimated_cost_usd=cost,
        context_window_size=ctx_window,
    )


# ---------------------------------------------------------------------------
# Non-streaming capture
# ---------------------------------------------------------------------------

def capture_response(raw: Dict[str, Any], latency_ms: float = 0.0) -> LLMResponse:
    """Convert a raw OpenAI-compatible JSON response into LLMResponse."""
    model = raw.get("model", _cfg.ai.model)
    choice = (raw.get("choices") or [{}])[0]
    message = choice.get("message") or choice.get("delta") or {}

    content = message.get("content") or ""
    finish_raw = choice.get("finish_reason", "stop") or "stop"
    try:
        finish = FinishReason(finish_raw)
    except ValueError:
        finish = FinishReason.STOP

    tool_calls = _parse_tool_calls(message.get("tool_calls") or [])
    usage = _build_token_usage(raw.get("usage") or {}, model)

    resp = LLMResponse(
        content=content,
        model=model,
        finish_reason=finish,
        usage=usage,
        tool_calls=tool_calls,
        latency_ms=latency_ms,
    )
    log.debug(
        f"[green]Captured response[/] model={model} tokens={usage.total_tokens} "
        f"latency={latency_ms:.0f}ms ctx={usage.context_utilization_pct:.1f}%"
    )
    return resp


# ---------------------------------------------------------------------------
# Streaming (SSE) capture
# ---------------------------------------------------------------------------

def buffer_streaming_response(
    event_iterator: Iterator[str],
    model: str = "",
    ttfb_callback: Optional[callable] = None,
) -> LLMResponse:
    """
    Consume an SSE stream (lines of 'data: {...}') and assemble one LLMResponse.

    event_iterator yields raw SSE lines as strings, e.g.:
        "data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}"
    """
    chunks: List[str] = []
    content_parts: List[str] = []
    tool_call_map: Dict[int, Dict] = {}
    finish_raw = "stop"
    model_seen = model or _cfg.ai.model
    first_chunk_received = False
    t_start = time.perf_counter()
    ttfb_ms = 0.0

    for line in event_iterator:
        line = line.strip()
        if not line or line == "data: [DONE]":
            continue
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
        else:
            payload = line

        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            log.debug(f"Skipping unparseable SSE chunk: {payload[:80]}")
            continue

        chunks.append(payload)

        if not first_chunk_received:
            ttfb_ms = (time.perf_counter() - t_start) * 1000
            first_chunk_received = True
            if ttfb_callback:
                ttfb_callback(ttfb_ms)

        model_seen = chunk.get("model", model_seen)
        choice = (chunk.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}
        finish_raw = choice.get("finish_reason") or finish_raw

        if text := delta.get("content"):
            content_parts.append(text)

        # Accumulate tool call deltas (streamed in pieces by index)
        for tc_delta in delta.get("tool_calls") or []:
            idx = tc_delta.get("index", 0)
            if idx not in tool_call_map:
                tool_call_map[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
            tc = tool_call_map[idx]
            tc["id"] = tc.get("id") or tc_delta.get("id", "")
            fn = tc_delta.get("function", {})
            tc["function"]["name"] += fn.get("name", "")
            tc["function"]["arguments"] += fn.get("arguments", "")

    latency_ms = (time.perf_counter() - t_start) * 1000
    tool_calls = _parse_tool_calls(list(tool_call_map.values()))

    try:
        finish = FinishReason(finish_raw)
    except ValueError:
        finish = FinishReason.STOP

    # Streaming responses don't always include usage; estimate from chunks
    usage = TokenUsage(context_window_size=_cfg.ai.context_window_for(model_seen))

    resp = LLMResponse(
        content="".join(content_parts),
        model=model_seen,
        finish_reason=finish,
        usage=usage,
        tool_calls=tool_calls,
        latency_ms=latency_ms,
        ttfb_ms=ttfb_ms,
        raw_chunks=chunks,
    )
    log.debug(
        f"[green]Buffered stream[/] model={model_seen} chunks={len(chunks)} "
        f"ttfb={ttfb_ms:.0f}ms total={latency_ms:.0f}ms"
    )
    return resp
