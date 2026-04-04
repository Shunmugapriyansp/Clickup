"""
AI Chat Page Object
===================
Playwright page object for a generic AI chat interface embedded in a web app.
Selectors are written generically; override per-app by subclassing.

Captures the last AI response text for use in semantic / safety assertions.
"""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from core.config import get_config
from core.logger import get_logger
from ui.pages.base_page import BasePage

log = get_logger(__name__)
_cfg = get_config()


class AIChatPage(BasePage):
    """
    Selectors target generic chat UI patterns.
    Override these class-level attributes in subclasses for specific apps.
    """

    # --- Selectors (override per-app) ---
    CHAT_INPUT = '[data-testid="chat-input"], textarea[placeholder*="message" i], #chat-input'
    SEND_BUTTON = '[data-testid="send-button"], button[aria-label*="send" i], button[type="submit"]'
    MESSAGE_LIST = '[data-testid="message-list"], .chat-messages, .message-list'
    AI_MESSAGE = '[data-testid="assistant-message"], .assistant-message, .ai-message'
    TYPING_INDICATOR = '[data-testid="typing-indicator"], .typing-indicator, .is-typing'
    CLEAR_BUTTON = '[data-testid="clear-chat"], button[aria-label*="clear" i]'
    ERROR_BANNER = '[data-testid="error-banner"], .error-message, .alert-error'

    def __init__(self, page: Page, chat_path: str = "/") -> None:
        super().__init__(page)
        self._chat_path = chat_path
        self._last_response: Optional[str] = None

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def open(self) -> None:
        self.navigate(self._chat_path)
        self.wait_for_selector(self.CHAT_INPUT)
        log.debug("Chat page opened and input ready.")

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def type_message(self, text: str) -> None:
        self.page.fill(self.CHAT_INPUT, "")  # clear first
        self.page.fill(self.CHAT_INPUT, text)
        log.debug(f"Typed message: {text[:60]}")

    def send_message(self) -> None:
        self.page.click(self.SEND_BUTTON)

    def send(self, text: str) -> str:
        """Type, send, wait for response, and return the response text."""
        self.type_message(text)
        self.send_message()
        return self.wait_for_response()

    def wait_for_response(self, timeout_ms: Optional[int] = None) -> str:
        """
        Wait for the typing indicator to appear then disappear,
        then return the last AI message text.
        """
        t = timeout_ms or _cfg.ui.default_timeout_ms

        # Wait for typing indicator (if exists in app)
        try:
            self.page.wait_for_selector(self.TYPING_INDICATOR, state="visible", timeout=5000)
            self.page.wait_for_selector(self.TYPING_INDICATOR, state="hidden", timeout=t)
        except PlaywrightTimeoutError:
            # App may not have a typing indicator — fall through
            pass

        # Wait for at least one AI message to be present
        self.page.wait_for_selector(self.AI_MESSAGE, state="visible", timeout=t)

        # Return the LAST assistant message
        messages = self.page.query_selector_all(self.AI_MESSAGE)
        text = messages[-1].inner_text().strip() if messages else ""
        self._last_response = text
        log.debug(f"AI response received: {text[:100]}")
        return text

    def get_last_response(self) -> Optional[str]:
        return self._last_response

    def get_all_messages(self) -> list:
        """Return all visible message texts in order."""
        elements = self.page.query_selector_all(
            f"{self.AI_MESSAGE}, [data-testid='user-message']"
        )
        return [el.inner_text().strip() for el in elements]

    def clear_chat(self) -> None:
        try:
            self.page.click(self.CLEAR_BUTTON, timeout=3000)
            log.debug("Chat cleared.")
        except PlaywrightTimeoutError:
            log.debug("No clear button found — skipping.")

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def assert_response_visible(self) -> None:
        self.assert_visible(self.AI_MESSAGE)

    def assert_no_error(self) -> None:
        if self.is_visible(self.ERROR_BANNER):
            error_text = self.get_text(self.ERROR_BANNER)
            raise AssertionError(f"Error banner visible in chat UI: '{error_text}'")

    def assert_response_contains(self, text: str) -> None:
        if self._last_response is None:
            raise AssertionError("No response has been captured yet.")
        if text.lower() not in self._last_response.lower():
            raise AssertionError(
                f"Expected '{text}' in response.\nActual: {self._last_response[:300]}"
            )

    def assert_response_not_contains(self, text: str) -> None:
        if self._last_response and text.lower() in self._last_response.lower():
            raise AssertionError(
                f"Forbidden text '{text}' found in response.\nActual: {self._last_response[:300]}"
            )
