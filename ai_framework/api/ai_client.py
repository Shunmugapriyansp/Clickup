"""
AI API Client
=============
OpenAI-compatible HTTP client built on httpx.
Supports both synchronous and streaming calls.

Designed to wrap any OpenAI-compatible endpoint:
  - OpenAI (gpt-4o, gpt-4o-mini, …)
  - Azure OpenAI
  - Anthropic via API proxy
  - Local models (Ollama, LM Studio, vLLM)
"""
from __future__ import annotations

import time
from typing import Iterator, List, Optional

import httpx

from core.config import get_config
from core.logger import get_logger
from core.response_capture import buffer_streaming_response, capture_response
from core.types import LLMResponse, Message, ToolCall

log = get_logger(__name__)
_cfg = get_config()


def _messages_to_dict(messages: List[Message]) -> list:
    result = []
    for m in messages:
        d: dict = {"role": m.role, "content": m.content}
        if m.tool_call_id:
            d["tool_call_id"] = m.tool_call_id
        if m.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.name, "arguments": str(tc.arguments)}}
                for tc in m.tool_calls
            ]
        result.append(d)
    return result


class AIClient:
    """
    Thin wrapper around the OpenAI Chat Completions API.

    Parameters
    ----------
    base_url : override the AI_BASE_URL env var
    api_key  : override the AI_API_KEY env var
    model    : default model for all calls
    timeout  : httpx timeout in seconds
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        self._base_url = (base_url or _cfg.ai.base_url).rstrip("/")
        self._api_key = api_key or _cfg.ai.api_key
        self._default_model = model or _cfg.ai.model
        self._http = httpx.Client(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Non-streaming chat
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        tools: Optional[list] = None,
    ) -> LLMResponse:
        payload = {
            "model": model or self._default_model,
            "messages": _messages_to_dict(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        t_start = time.perf_counter()
        resp = self._http.post(f"{self._base_url}/chat/completions", json=payload)
        latency_ms = (time.perf_counter() - t_start) * 1000

        resp.raise_for_status()
        return capture_response(resp.json(), latency_ms=latency_ms)

    # ------------------------------------------------------------------
    # Streaming chat
    # ------------------------------------------------------------------

    def chat_stream(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        payload = {
            "model": model or self._default_model,
            "messages": _messages_to_dict(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        ttfb_holder: list = [0.0]

        def ttfb_callback(ms: float) -> None:
            ttfb_holder[0] = ms

        with self._http.stream(
            "POST",
            f"{self._base_url}/chat/completions",
            json=payload,
        ) as stream:
            return buffer_streaming_response(
                event_iterator=stream.iter_lines(),
                model=model or self._default_model,
                ttfb_callback=ttfb_callback,
            )

    # ------------------------------------------------------------------
    # Simple prompt helper
    # ------------------------------------------------------------------

    def prompt(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """Convenience wrapper for single-turn prompts."""
        msgs: List[Message] = []
        if system_prompt:
            msgs.append(Message(role="system", content=system_prompt))
        msgs.append(Message(role="user", content=user_message))
        return self.chat(msgs, **kwargs)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "AIClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
