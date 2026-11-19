"""Text formatting helpers for the token-usage plugin."""

from __future__ import annotations

from typing import Any


def _fmt_int(n: Any) -> str:
    """Format a number with K/M/B/T suffixes for readability.

    Small values (< 1,000) stay as plain integers; larger values get a
    single-decimal suffix (12.3K, 15.1M, 2.3B, 0.4T).
    """
    try:
        value = int(n)
    except (TypeError, ValueError):
        return str(n)

    abs_value = abs(value)
    sign = "-" if value < 0 else ""

    if abs_value < 1_000:
        return f"{sign}{abs_value:,}"
    if abs_value < 1_000_000:
        return f"{sign}{value / 1_000:,.1f}K"
    if abs_value < 1_000_000_000:
        return f"{sign}{value / 1_000_000:,.1f}M"
    if abs_value < 1_000_000_000_000:
        return f"{sign}{value / 1_000_000_000:,.1f}B"
    return f"{sign}{value / 1_000_000_000_000:,.1f}T"


def _fmt_cost(n: Any, currency: str = "USD") -> str:
    try:
        return f"{currency} {float(n):,.4f}"
    except (TypeError, ValueError):
        return f"{currency} 0.0000"


def _fmt_ts(ts: Any) -> str:
    if ts is None:
        return ""
    try:
        import datetime
        return datetime.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(ts)


def _fmt_share(part: Any, whole: Any) -> str:
    try:
        p = float(part or 0)
        w = float(whole or 0)
        if w <= 0:
            return "0.0"
        return f"{p / w * 100:.1f}"
    except (TypeError, ValueError):
        return "0.0"


def _truncate(s: Any, width: int = 24) -> str:
    s = str(s)
    if len(s) <= width:
        return s
    return s[: width - 1] + "…"


def _box_table(title: str | None, headers: list[str],
               rows: list[list[str]]) -> str:
    if not headers:
        return ""
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("")

    top = "┌" + "┬".join("─" * (w + 2) for w in widths) + "┐"
    sep = "├" + "┼".join("─" * (w + 2) for w in widths) + "┤"
    bot = "└" + "┴".join("─" * (w + 2) for w in widths) + "┘"

    lines.append(top)
    lines.append("│" + "│".join(f" {str(h).ljust(w)} " for h, w in zip(headers, widths)) + "│")
    lines.append(sep)
    for row in rows:
        lines.append("│" + "│".join(f" {str(c).ljust(w)} " for c, w in zip(row, widths)) + "│")
    lines.append(bot)
    return "\n".join(lines)
