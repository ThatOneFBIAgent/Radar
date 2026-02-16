"""
Logging configuration for Radar.

Sets up structured logging with a clean, TUI-style format.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal


_LOG_FORMAT = "%(asctime)s │ %(levelname)-8s │ %(name)-24s │ %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def setup_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
) -> None:
    """Configure the root logger for the application.

    Uses a clean, monospaced-friendly format with box-drawing separators.
    """
    numeric_level = getattr(logging, level, logging.INFO)

    # Remove any existing handlers
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root.setLevel(numeric_level)
    root.addHandler(console)

    # Quiet noisy libraries
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging initialized — level=%s", level
    )
