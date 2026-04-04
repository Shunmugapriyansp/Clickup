"""
Structured logger using Rich for human-readable terminal output.
All framework modules import get_logger() from here.
"""
from __future__ import annotations

import logging
import sys
from functools import lru_cache
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

console = Console(stderr=True)


def _build_handler() -> RichHandler:
    return RichHandler(
        console=console,
        show_time=True,
        show_level=True,
        show_path=True,
        markup=True,
        rich_tracebacks=True,
    )


@lru_cache(maxsize=None)
def get_logger(name: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name or "ai_framework")
    if not logger.handlers:
        logger.addHandler(_build_handler())
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
