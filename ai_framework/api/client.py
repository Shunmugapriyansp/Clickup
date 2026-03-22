"""
Base HTTP Client
================
Generic REST client for non-AI API testing (e.g., ClickUp REST API).
Provides request helpers, response assertions, and timing capture.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx

from core.logger import get_logger

log = get_logger(__name__)


class RestClient:
    """
    Thin httpx wrapper for REST API testing.

    Example
    -------
    client = RestClient(base_url="https://api.clickup.com/api/v2",
                        headers={"Authorization": "Bearer <token>"})
    resp = client.get("/task/abc123")
    client.assert_status(resp, 200)
    """

    def __init__(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            headers=headers or {},
            timeout=timeout,
        )
        self._last_latency_ms: float = 0.0

    # ------------------------------------------------------------------
    # HTTP verbs
    # ------------------------------------------------------------------

    def get(self, path: str, params: Optional[dict] = None, **kwargs) -> httpx.Response:
        return self._request("GET", path, params=params, **kwargs)

    def post(self, path: str, json: Optional[dict] = None, **kwargs) -> httpx.Response:
        return self._request("POST", path, json=json, **kwargs)

    def put(self, path: str, json: Optional[dict] = None, **kwargs) -> httpx.Response:
        return self._request("PUT", path, json=json, **kwargs)

    def patch(self, path: str, json: Optional[dict] = None, **kwargs) -> httpx.Response:
        return self._request("PATCH", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self._request("DELETE", path, **kwargs)

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def assert_status(self, response: httpx.Response, expected: int) -> None:
        if response.status_code != expected:
            raise AssertionError(
                f"Expected HTTP {expected}, got {response.status_code}.\n"
                f"Body: {response.text[:500]}"
            )

    def assert_json_key(self, response: httpx.Response, key: str, expected: Any = None) -> Any:
        data = response.json()
        if key not in data:
            raise AssertionError(f"Key '{key}' not found in response JSON: {list(data.keys())}")
        value = data[key]
        if expected is not None and value != expected:
            raise AssertionError(f"Key '{key}': expected '{expected}', got '{value}'")
        return value

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    @property
    def last_latency_ms(self) -> float:
        return self._last_latency_ms

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self._base_url}/{path.lstrip('/')}"
        t_start = time.perf_counter()
        resp = self._http.request(method, url, **kwargs)
        self._last_latency_ms = (time.perf_counter() - t_start) * 1000
        log.debug(
            f"{method} {url} → {resp.status_code} ({self._last_latency_ms:.0f}ms)"
        )
        return resp

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "RestClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
