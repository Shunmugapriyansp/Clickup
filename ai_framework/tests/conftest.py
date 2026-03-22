"""
pytest conftest — shared fixtures for the full AI automation framework.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from api.ai_client import AIClient
from api.client import RestClient
from core.config import get_config
from reporting.quality_report import QualityReporter

_cfg = get_config()


# ---------------------------------------------------------------------------
# AI client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def ai_client() -> AIClient:
    """Session-scoped AI client — one HTTP connection pool per test run."""
    with AIClient() as client:
        yield client


@pytest.fixture(scope="function")
def fresh_ai_client() -> AIClient:
    """Function-scoped client — use when you need test isolation."""
    with AIClient() as client:
        yield client


# ---------------------------------------------------------------------------
# REST API client fixture (ClickUp or any REST target)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def api_client() -> RestClient:
    base = _cfg.ui.base_url.rstrip("/") + "/api/v2"
    headers = {"Authorization": f"Bearer {_cfg.ai.api_key}"}
    with RestClient(base_url=base, headers=headers) as client:
        yield client


# ---------------------------------------------------------------------------
# Playwright browser / page fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser() -> Browser:
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=_cfg.ui.headless,
            slow_mo=_cfg.ui.slow_mo_ms,
        )
        yield br
        br.close()


@pytest.fixture(scope="function")
def context(browser: Browser) -> BrowserContext:
    ctx = browser.new_context(
        viewport={"width": _cfg.ui.viewport_width, "height": _cfg.ui.viewport_height},
    )
    yield ctx
    ctx.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    pg = context.new_page()
    pg.set_default_timeout(_cfg.ui.default_timeout_ms)
    yield pg


# ---------------------------------------------------------------------------
# Quality reporter fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def quality_reporter() -> QualityReporter:
    reporter = QualityReporter()
    yield reporter
    reporter.save()   # write to disk after all tests finish


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line("markers", "ai: mark test as AI/LLM test")
    config.addinivalue_line("markers", "security: mark test as security test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "ui: mark test as UI test")
    config.addinivalue_line("markers", "api: mark test as API test")


def pytest_runtest_makereport(item, call):
    """Attach screenshot on UI test failure."""
    if call.when == "call" and call.excinfo:
        page_fixture = item.funcargs.get("page")
        if page_fixture:
            try:
                path = page_fixture.screenshot()
                item.add_report_section("call", "screenshot", str(path))
            except Exception:
                pass
