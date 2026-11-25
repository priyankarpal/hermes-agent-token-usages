"""ANSI color wrapper with TTY and NO_COLOR detection."""

from __future__ import annotations

import os
import sys


class Color:
    """ANSI color wrapper with TTY and NO_COLOR detection.

    Colours are only emitted when stdout is a TTY and NO_COLOR is not set.
    """

    # ANSI escape codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    def __init__(self) -> None:
        self._enabled = self._detect_enabled()

    def _detect_enabled(self) -> bool:
        """Check if colors should be enabled."""
        # Respect NO_COLOR standard: https://no-color.org/
        if os.environ.get("NO_COLOR"):
            return False
        # Only enable on TTY
        return sys.stdout.isatty()

    @property
    def is_enabled(self) -> bool:
        """Return True if colors are enabled."""
        return self._enabled

    def wrap(self, text: str, style: str) -> str:
        """Wrap text with ANSI style if enabled, otherwise return plain text."""
        if not self._enabled:
            return text
        return f"{style}{text}{self.RESET}"