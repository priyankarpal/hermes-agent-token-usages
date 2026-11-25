"""Daily heatmap rendering (GitHub-style 12-week contribution grid)."""

from __future__ import annotations

import datetime
from typing import Any

from .color import Color


# GitHub-style green shades (ANSI 256-color codes)
HEATMAP_COLORS = {
    0: None,           # Empty - no color
    1: 157,            # Light green (#9be9a8)
    2: 76,             # Medium green (#40c463)
    3: 48,             # Dark green (#30a14e)
    4: 22,             # Darker green (#216e39)
}

# Unicode block characters for heatmap cells
HEATMAP_CHARS = {
    0: " ",            # Empty
    1: "\u2591",       # Light shade (░)
    2: "\u2592",       # Medium shade (▒)
    3: "\u2593",       # Dark shade (▓)
    4: "\u2588",       # Full block (█)
}

# Day abbreviations (Monday first)
DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Month abbreviations
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def week_start(date: datetime.date) -> datetime.date:
    """Return the Monday of the week containing date."""
    return date - datetime.timedelta(days=date.weekday())


def heatmap_window(today: datetime.date) -> tuple[datetime.date, datetime.date]:
    """Return (start_date, end_date) for 12-week heatmap ending on today."""
    end_date = today
    start_date = week_start(today) - datetime.timedelta(weeks=11)
    return start_date, end_date


def intensity_level(value: int, peak: int) -> int:
    """Compute heatmap intensity level (0-4) from value and peak.

    Formula: ceil(value * 4 / peak) giving levels 1-4, 0 for empty days.
    """
    if value <= 0:
        return 0
    if peak <= 0:
        return 1
    # ceil(value * 4 / peak)
    level = (value * 4 + peak - 1) // peak
    return min(max(level, 1), 4)


def render_heatmap(buckets: list[dict[str, Any]], width: int, color: Color) -> str:
    """Render GitHub-style 12-week daily heatmap.

    Args:
        buckets: List of daily buckets with 'bucket' (YYYY-MM-DD) and 'total_tokens'.
        width: Terminal width for layout.
        color: Color instance for ANSI output.

    Returns:
        Formatted heatmap string.
    """
    if not buckets:
        return "No data for heatmap"

    # Build lookup: date_str -> total_tokens
    daily_totals: dict[str, int] = {}
    peak = 0
    for b in buckets:
        bucket = b.get("bucket", "")
        total = int(b.get("total_tokens", 0))
        if bucket and total > 0:
            daily_totals[bucket] = total
            peak = max(peak, total)

    # Determine heatmap window (12 weeks ending today)
    today = datetime.date.today()
    start_date, end_date = heatmap_window(today)

    # Generate 12 weeks of dates (Mon-Sun)
    weeks: list[list[datetime.date]] = []
    current_monday = start_date
    for _ in range(12):
        week = [current_monday + datetime.timedelta(days=i) for i in range(7)]
        weeks.append(week)
        current_monday += datetime.timedelta(weeks=1)

    # Build month labels - track which weeks belong to which month
    month_spans: list[tuple[int, int, str]] = []  # (start_week, end_week, label)
    prev_month = None
    span_start = 0
    for week_idx, week in enumerate(weeks):
        # Check each day in the week for month changes
        for day in week:
            if day > today:
                break
            month = day.month
            if month != prev_month:
                if prev_month is not None:
                    month_spans.append((span_start, week_idx - 1, MONTH_LABELS[prev_month - 1]))
                prev_month = month
                span_start = week_idx
    # Close the last span
    if prev_month is not None:
        month_spans.append((span_start, 11, MONTH_LABELS[prev_month - 1]))

    # Render header with month labels
    lines: list[str] = []
    lines.append("TOKENS BY DAY \u00b7 LAST 12 WEEKS")
    lines.append("\u2500" * min(width, 80))  # Separator line

    # Month label row - center each label over its weeks
    month_row = "      "  # Space for day labels
    for week_idx in range(12):
        # Find which span this week belongs to
        label = ""
        for start, end, span_label in month_spans:
            if start <= week_idx <= end:
                # Only show label on the first week of the span
                if week_idx == start:
                    label = span_label
                break
        # Each week takes 4 chars (2 for cell + 2 spacing), center 3-char label
        if label:
            month_row += f" {label:^3}"
        else:
            month_row += "    "
    lines.append(month_row)

    # Day rows (Mon-Sun)
    for day_idx in range(7):
        day_label = DAY_LABELS[day_idx]
        row = f"{day_label:4} "
        for week_idx in range(12):
            date = weeks[week_idx][day_idx]
            date_str = date.strftime("%Y-%m-%d")

            if date > today:
                # Future dates - blank
                cell = " \u00b7"
            elif date_str in daily_totals:
                value = daily_totals[date_str]
                level = intensity_level(value, peak)
                char = HEATMAP_CHARS[level]
                if color.is_enabled and HEATMAP_COLORS[level]:
                    cell = color.wrap(char, f"\033[38;5;{HEATMAP_COLORS[level]}m")
                else:
                    cell = char
                cell = f" {cell}"
            else:
                # No data for this day
                cell = " \u00b7"
            row += cell
        lines.append(row)

    # Legend
    legend = "Less \u00b7"
    for level in range(1, 5):
        char = HEATMAP_CHARS[level]
        if color.is_enabled and HEATMAP_COLORS[level]:
            legend += f" {color.wrap(char, f'\033[38;5;{HEATMAP_COLORS[level]}m')}"
        else:
            legend += f" {char}"
    legend += " \u00b7 More"
    lines.append("")
    lines.append(legend)

    return "\n".join(lines)