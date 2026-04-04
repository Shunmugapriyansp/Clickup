"""
Base Page Object
================
All page classes extend BasePage which holds the Playwright Page reference
and provides shared utilities (navigation, waits, screenshot on failure).
Mirrors the existing Cypress POM style from the Clickup Cypress project.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, expect

from core.config import get_config
from core.logger import get_logger

log = get_logger(__name__)
_cfg = get_config()


class BasePage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self._base_url = _cfg.ui.base_url

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, path: str = "") -> None:
        url = self._base_url.rstrip("/") + "/" + path.lstrip("/")
        log.debug(f"Navigating to {url}")
        self.page.goto(url, wait_until="domcontentloaded")

    # ------------------------------------------------------------------
    # Element helpers
    # ------------------------------------------------------------------

    def click(self, selector: str, timeout: Optional[int] = None) -> None:
        self.page.click(selector, timeout=timeout or _cfg.ui.default_timeout_ms)

    def fill(self, selector: str, text: str) -> None:
        self.page.fill(selector, text)

    def type_text(self, selector: str, text: str, delay: int = 50) -> None:
        """Type with a human-like delay (useful for rich-text editors)."""
        self.page.type(selector, text, delay=delay)

    def get_text(self, selector: str) -> str:
        return self.page.inner_text(selector).strip()

    def wait_for_selector(self, selector: str, timeout: Optional[int] = None) -> None:
        self.page.wait_for_selector(
            selector,
            state="visible",
            timeout=timeout or _cfg.ui.default_timeout_ms,
        )

    def is_visible(self, selector: str) -> bool:
        return self.page.is_visible(selector)

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def assert_visible(self, selector: str) -> None:
        expect(self.page.locator(selector)).to_be_visible()

    def assert_text_contains(self, selector: str, text: str) -> None:
        expect(self.page.locator(selector)).to_contain_text(text)

    def assert_url_contains(self, fragment: str) -> None:
        expect(self.page).to_have_url(f"*{fragment}*")

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def screenshot(self, name: str = "screenshot") -> Path:
        reports = Path(_cfg.reports_dir) / "screenshots"
        reports.mkdir(parents=True, exist_ok=True)
        path = reports / f"{name}.png"
        self.page.screenshot(path=str(path))
        log.debug(f"Screenshot saved: {path}")
        return path
