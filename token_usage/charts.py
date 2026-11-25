"""Month and year bar chart rendering."""

from __future__ import annotations

import datetime
from typing import Any

from .color import Color


# -- Formatters -------------------------------------------------------------

def fmt_int(n: Any) -> str:
    """Format a number with K/M/B/T suffixes for readability."""
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


def month_window(today: datetime.date) -> list[datetime.date]:
    """Return list of 6 month start dates (first day of month) ending with today's month."""
    months = []
    current = datetime.date(today.year, today.month, 1)
    for _ in range(6):
        months.append(current)
        # Go to previous month
        if current.month == 1:
            current = datetime.date(current.year - 1, 12, 1)
        else:
            current = datetime.date(current.year, current.month - 1, 1)
    return list(reversed(months))  # Oldest first


def year_window(today: datetime.date) -> list[int]:
    """Return list of 3 years ending with today's year."""
    return [today.year - 2, today.year - 1, today.year]


def render_bar_chart(buckets: list[dict[str, Any]], granularity: str,
                     cfg: dict[str, Any], currency: str,
                     width: int, color: Color) -> str:
    """Render horizontal bar chart for month or year view.

    Args:
        buckets: List of time buckets with 'bucket' and 'total_tokens'.
        granularity: "month" or "year".
        cfg: Config dict for labels.
        currency: Currency label.
        width: Terminal width.
        color: Color instance.

    Returns:
        Formatted bar chart string.
    """
    if not buckets:
        return "No data for bar chart"

    # Build lookup: bucket -> total_tokens
    bucket_totals: dict[str, int] = {}
    for b in buckets:
        bucket = b.get("bucket", "")
        total = int(b.get("total_tokens", 0))
        if bucket:
            bucket_totals[bucket] = bucket_totals.get(bucket, 0) + total

    # Grand total for share calculation
    grand_total = sum(bucket_totals.values())

    # Get window of periods
    today = datetime.date.today()
    if granularity == "month":
        periods = month_window(today)
        period_labels = [p.strftime("%Y-%m") for p in periods]
        title = "TOKENS BY MONTH \u00b7 LAST 6 MONTHS"
    else:  # year
        periods = year_window(today)
        period_labels = [str(y) for y in periods]
        title = "TOKENS BY YEAR \u00b7 LAST 3 YEARS"

    lines: list[str] = []
    lines.append(title)
    lines.append("\u2500" * min(width, 80))

    # Header
    L = lambda k: cfg.get("token_plugin", {}).get("labels", {}).get(k, k)
    lines.append(f"{'Period':>12}  {'Amount':>10}  {'Share':>6}  Bar")

    # Bar width (responsive)
    bar_width = min(30, max(10, width - 40))

    for period_label in period_labels:
        total = bucket_totals.get(period_label, 0)
        share = (total / grand_total * 100) if grand_total > 0 else 0.0

        # Share bar (10 chars like per-model table)
        share_filled = int(share / 10)
        share_bar = "\u2588" * share_filled + "\u2591" * (10 - share_filled)

        # Color for share bar (use green shades)
        if color.is_enabled and share_filled > 0:
            # Use 4 green shades based on share
            share_level = min(share_filled, 4)
            green_codes = {1: 157, 2: 76, 3: 48, 4: 22}
            if share_level in green_codes:
                share_bar = color.wrap(share_bar, f"\033[38;5;{green_codes[share_level]}m")

        amount_str = fmt_int(total)
        share_str = f"{share:.1f}%"

        lines.append(f"{period_label:>12}  {amount_str:>10}  {share_str:>6}  {share_bar}")

    return "\n".join(lines)