"""Presentation: formatting + text/JSON rendering.

Depends only on config for user-facing labels.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .config import cfg_val, label


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


def fmt_cost(n: Any, currency: str = "USD") -> str:
    if n is None:
        return "—"
    try:
        return f"{currency} {float(n):,.4f}"
    except (TypeError, ValueError):
        return f"{currency} 0.0000"


def fmt_ts(ts: Any) -> str:
    if ts is None:
        return ""
    try:
        import datetime
        return datetime.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(ts)


def fmt_share(part: Any, whole: Any) -> str:
    try:
        p = float(part or 0)
        w = float(whole or 0)
        if w <= 0:
            return "0.0"
        return f"{p / w * 100:.1f}"
    except (TypeError, ValueError):
        return "0.0"


def fmt_ratio(part: Any, whole: Any) -> str:
    """Share of *part* against *whole* as a percentage, or ``n/a`` when unknown.

    Used for the cache-read ratio (cache reads vs real tokens), which is often
    the most informative number in the report.
    """
    # Explicit None check: if part is None, the ratio is unknown
    if part is None:
        return "n/a"
    try:
        p = float(part)
        w = float(whole or 0)
        if w <= 0:
            return "n/a"
        return f"{p / w * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def truncate(s: Any, width: int = 24) -> str:
    s = str(s)
    if len(s) <= width:
        return s
    return s[: width - 1] + "…"


def box_table(title: Optional[str], headers: list[str],
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


class TableRenderer:
    """Responsive table renderer with column dropping for narrow terminals.
    
    Columns are dropped in priority order (lowest priority first) until
    the table fits within the specified width.
    """
    
    def __init__(
        self,
        headers: list[str],
        rows: list[list[str]],
        drop_priority: list[list[int]],
        min_width: int = 40,
    ) -> None:
        self.headers = list(headers)
        self.rows = [list(r) for r in rows]
        self.drop_priority = drop_priority
        self.min_width = min_width
        self._active_headers = list(headers)
        self._active_rows = [list(r) for r in rows]
        self._active_indices = list(range(len(headers)))
    
    def _compute_widths(self) -> list[int]:
        widths = [len(str(h)) for h in self._active_headers]
        for row in self._active_rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
        return widths
    
    def _table_width(self, widths: list[int]) -> int:
        # Box drawing: corners + separators + padding
        # "┌" + "┬".join("─" * (w + 2)) + "┐" = 1 + sum(w+2) + (n-1) + 1 = sum(w) + 3n
        return sum(widths) + 3 * len(widths)
    
    def _drop_columns(self) -> bool:
        """Drop the next priority group of columns. Returns True if any dropped."""
        for group in self.drop_priority:
            # Filter to only indices that are still active
            droppable = [idx for idx in group if idx in self._active_indices]
            if not droppable:
                continue
            # Drop all in this group
            new_active_headers = []
            new_active_rows = []
            new_active_indices = []
            for i, hdr in enumerate(self._active_headers):
                orig_idx = self._active_indices[i]
                if orig_idx not in droppable:
                    new_active_headers.append(hdr)
                    new_active_indices.append(orig_idx)
                # else: drop this column
            # Drop from rows
            new_active_rows = []
            for row in self._active_rows:
                new_row = [cell for i, cell in enumerate(row) if self._active_indices[i] not in droppable]
                new_active_rows.append(new_row)
            
            self._active_headers = new_active_headers
            self._active_rows = new_active_rows
            self._active_indices = new_active_indices
            return True
        return False
    
    def render(self, width: int) -> str:
        """Render table fitting within width, dropping columns as needed."""
        if width < self.min_width:
            width = self.min_width
        
        # Try to fit by dropping columns
        while True:
            widths = self._compute_widths()
            table_w = self._table_width(widths)
            if table_w <= width:
                break
            if not self._drop_columns():
                # Can't drop more, render anyway
                break
        
        # Build the table with current active columns
        widths = self._compute_widths()
        lines: list[str] = []
        top = "┌" + "┬".join("─" * (w + 2) for w in widths) + "┐"
        sep = "├" + "┼".join("─" * (w + 2) for w in widths) + "┤"
        bot = "└" + "┴".join("─" * (w + 2) for w in widths) + "┘"
        lines.append(top)
        lines.append("│" + "│".join(f" {str(h).ljust(w)} " for h, w in zip(self._active_headers, widths)) + "│")
        lines.append(sep)
        for row in self._active_rows:
            lines.append("│" + "│".join(f" {str(c).ljust(w)} " for c, w in zip(row, widths)) + "│")
        lines.append(bot)
        return "\n".join(lines)


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
        import sys
        import os
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


def render_totals_panel(totals: dict[str, Any], cfg: dict[str, Any],
                        currency: str, color: Color) -> str:
    """Render totals as a compact key-value panel (no box table)."""
    L = lambda k: label(cfg, k)
    total_tokens = int(totals.get("total_tokens", 0))
    cache_read = totals.get("cache_read_tokens", 0)
    input_tokens = totals.get("input_tokens", 0)
    cache_hit_rate = None
    if cache_read + input_tokens > 0:
        cache_hit_rate = (cache_read / (cache_read + input_tokens)) * 100.0
    
    rows = [
        (f"{L('hdr_sessions')}:", fmt_int(totals.get("sessions", 0)), None),
        (f"{L('hdr_input')}:", fmt_int(totals.get("input_tokens", 0)), color.GREEN),
        (f"{L('hdr_output')}:", fmt_int(totals.get("output_tokens", 0)), color.GREEN),
        (f"{L('hdr_cache_read')}:", fmt_int(cache_read), color.CYAN),
        (f"{L('hdr_cache_multiplier')}:", fmt_ratio(cache_read, total_tokens), color.CYAN),
        (f"{L('hdr_cache_hit_rate')}:", fmt_ratio(cache_hit_rate, 100), color.CYAN),
        (f"{L('hdr_cache_write')}:", fmt_int(totals.get("cache_write_tokens", 0)), None),
        (f"{L('hdr_reasoning')}:", fmt_int(totals.get("reasoning_tokens", 0)), None),
        (f"{L('hdr_total')}:", fmt_int(total_tokens), color.BOLD),
        (f"{L('hdr_api_calls')}:", fmt_int(totals.get("api_calls", 0)), None),
        (f"{L('hdr_est_cost')} ({currency}):", fmt_cost(totals.get("est_cost"), currency), color.YELLOW),
        (f"{L('hdr_actual_cost')} ({currency}):", fmt_cost(totals.get("actual_cost"), currency), color.YELLOW),
    ]
    
    # Format as "Label: Value" with aligned labels
    max_label_len = max(len(label) for label, _, _ in rows)
    lines = []
    for label_text, value, style in rows:
        padded_label = label_text.ljust(max_label_len)
        styled_value = color.wrap(value, style) if style else value
        lines.append(f"{padded_label}  {styled_value}")
    
    return "\n".join(lines)


def render_models_table(models: list[dict[str, Any]], grand_total: int,
                        cfg: dict[str, Any], currency: str,
                        color: Color, width: int) -> str:
    """Render per-model table with share bars and responsive columns."""
    L = lambda k: label(cfg, k)
    
    rows = []
    for m in models:
        share = m.get("total_tokens", 0) / grand_total * 100 if grand_total > 0 else 0
        share_filled = int(share / 10)
        share_bar = "█" * share_filled + "░" * (10 - share_filled)
        share_display = f"{share_bar} {share:.1f}%"
        
        cache_read = m.get("cache_read_tokens", 0)
        input_tokens = m.get("input_tokens", 0)
        total_tokens = m.get("total_tokens", 0)
        cache_hit_rate = None
        if cache_read + input_tokens > 0:
            cache_hit_rate = (cache_read / (cache_read + input_tokens)) * 100.0
        
        cache_multiplier = fmt_ratio(cache_read, total_tokens)
        cache_hit_rate_fmt = fmt_ratio(cache_hit_rate, 100)
        
        rows.append([
            m.get("model", ""),
            fmt_int(m.get("sessions", 0)),
            fmt_int(m.get("input_tokens", 0)),
            fmt_int(m.get("output_tokens", 0)),
            fmt_int(cache_read),
            fmt_ratio(cache_read, total_tokens),
            fmt_ratio(cache_hit_rate, 100),
            fmt_int(total_tokens),
            share_display,
            fmt_int(m.get("api_calls", 0)),
            fmt_cost(m.get("est_cost"), currency),
        ])
    
    headers = [L("hdr_model"), L("hdr_sessions"), L("hdr_input"), L("hdr_output"),
               L("hdr_cache_read"), L("hdr_cache_multiplier"), L("hdr_cache_hit_rate"),
               L("hdr_total"), L("hdr_share"), L("hdr_api_calls"),
               f"{L('hdr_est_cost')} ({currency})"]
    
    # Column drop priority: [API Calls, Est. Cost] -> [Cache Hit Rate, Cache Multiplier] -> [Output, Cache Read]
    # Indices: API Calls=9, Est. Cost=10, Cache Hit Rate=6, Cache Multiplier=5, Output=3, Cache Read=4
    drop_priority = [[9, 10], [6, 5], [3, 4]]
    
    renderer = TableRenderer(headers, rows, drop_priority=drop_priority)
    return renderer.render(width)


def render_sessions_table(sessions: list[dict[str, Any]],
                          current_session: dict[str, Any] | None,
                          cfg: dict[str, Any], currency: str,
                          color: Color, width: int) -> str:
    """Render per-session table with current session pinned at top."""
    L = lambda k: label(cfg, k)
    
    # Pin current session at top
    cur_id = current_session.get("id") if current_session else None
    current = None
    others = []
    for s in sessions:
        if s.get("id") == cur_id:
            current = s
        else:
            others.append(s)
    
    # Sort others by total_tokens desc
    others.sort(key=lambda x: x.get("total_tokens", 0), reverse=True)
    
    # Build ordered list with current first
    ordered_sessions = []
    if current:
        ordered_sessions.append(current)
    ordered_sessions.extend(others)
    
    rows = []
    for i, s in enumerate(ordered_sessions):
        is_current = (i == 0 and current is not None)
        cache_read = s.get("cache_read_tokens", 0)
        input_tokens = s.get("input_tokens", 0)
        total_tokens = s.get("total_tokens", 0)
        cache_hit_rate = None
        if cache_read + input_tokens > 0:
            cache_hit_rate = (cache_read / (cache_read + input_tokens)) * 100.0
        
        session_id = s.get("id", "")
        if is_current:
            session_id = "● " + session_id
        
        rows.append([
            truncate(session_id, 24),
            s.get("model", ""),
            fmt_ts(s.get("started_at")),
            fmt_ts(s.get("last_activity_at")),
            fmt_int(s.get("input_tokens", 0)),
            fmt_int(s.get("output_tokens", 0)),
            fmt_int(cache_read),
            fmt_ratio(cache_read, total_tokens),
            fmt_ratio(cache_hit_rate, 100),
            fmt_int(s.get("reasoning_tokens", 0)),
            fmt_int(total_tokens),
            fmt_int(s.get("api_call_count", 0)),
            fmt_cost(s.get("est_cost"), currency),
        ])
    
    headers = [L("hdr_session"), L("hdr_model"), L("hdr_started"), L("hdr_last_activity"),
               L("hdr_input"), L("hdr_output"), L("hdr_cache_read"),
               L("hdr_cache_multiplier"), L("hdr_cache_hit_rate"),
               L("hdr_reasoning"), L("hdr_total"), L("hdr_api_calls"),
               f"{L('hdr_est_cost')} ({currency})"]
    
    # Column drop priority: [API Calls, Reasoning, Est. Cost] -> [Cache Hit Rate, Cache Multiplier] -> [Output, Cache Read]
    # Indices: API Calls=11, Reasoning=10, Est. Cost=12, Cache Hit Rate=8, Cache Multiplier=7, Output=5, Cache Read=6
    drop_priority = [[11, 10, 12], [8, 7], [5, 6]]
    
    renderer = TableRenderer(headers, rows, drop_priority=drop_priority)
    return renderer.render(width)


# -- Renderers --------------------------------------------------------------

def _render_totals(totals: dict[str, Any], cfg: dict[str, Any],
                   currency: str) -> str:
    L = lambda k: label(cfg, k)
    total_tokens = int(totals.get("total_tokens", 0))
    cache_read = totals.get("cache_read_tokens", 0)
    input_tokens = totals.get("input_tokens", 0)
    cache_hit_rate = None
    if cache_read + input_tokens > 0:
        cache_hit_rate = (cache_read / (cache_read + input_tokens)) * 100.0
    rows = [
        [L("hdr_sessions"), fmt_int(totals.get("sessions", 0))],
        [L("hdr_input"), fmt_int(totals.get("input_tokens", 0))],
        [L("hdr_output"), fmt_int(totals.get("output_tokens", 0))],
        [L("hdr_cache_read"), fmt_int(cache_read)],
        [L("hdr_cache_multiplier"), fmt_ratio(cache_read, total_tokens)],
        [L("hdr_cache_hit_rate"), fmt_ratio(cache_hit_rate, 100)],
        [L("hdr_cache_write"), fmt_int(totals.get("cache_write_tokens", 0))],
        [L("hdr_reasoning"), fmt_int(totals.get("reasoning_tokens", 0))],
        [L("hdr_total"), fmt_int(total_tokens)],
        [L("hdr_api_calls"), fmt_int(totals.get("api_calls", 0))],
        [f"{L('hdr_est_cost')} ({currency})", fmt_cost(totals.get("est_cost"), currency)],
        [f"{L('hdr_actual_cost')} ({currency})", fmt_cost(totals.get("actual_cost"), currency)],
    ]
    return box_table(L("totals_title"), [L("hdr_sessions"), "Value"], rows)


def _render_models(models: list[dict[str, Any]], grand_total: int,
                   cfg: dict[str, Any], currency: str) -> str:
    L = lambda k: label(cfg, k)
    rows: list[list[str]] = []
    for m in models:
        cache_read = m.get("cache_read_tokens", 0)
        input_tokens = m.get("input_tokens", 0)
        total_tokens = m.get("total_tokens", 0)
        cache_hit_rate = None
        if cache_read + input_tokens > 0:
            cache_hit_rate = (cache_read / (cache_read + input_tokens)) * 100.0
        rows.append([
            m.get("model", ""),
            fmt_int(m.get("sessions", 0)),
            fmt_int(m.get("input_tokens", 0)),
            fmt_int(m.get("output_tokens", 0)),
            fmt_int(cache_read),
            fmt_ratio(cache_read, total_tokens),
            fmt_ratio(cache_hit_rate, 100),
            fmt_int(total_tokens),
            fmt_share(total_tokens, grand_total),
            fmt_int(m.get("api_calls", 0)),
            fmt_cost(m.get("est_cost"), currency),
        ])
    headers = [L("hdr_model"), L("hdr_sessions"), L("hdr_input"), L("hdr_output"),
               L("hdr_cache_read"), L("hdr_cache_multiplier"), L("hdr_cache_hit_rate"), L("hdr_total"), L("hdr_share"),
               L("hdr_api_calls"), f"{L('hdr_est_cost')} ({currency})"]
    return box_table(L("model_title"), headers, rows)


def _render_sessions(sessions: list[dict[str, Any]], cfg: dict[str, Any],
                     currency: str,
                     current_session: Optional[dict[str, Any]] = None) -> str:
    L = lambda k: label(cfg, k)
    cur_id = current_session.get("id") if current_session else None
    rows: list[list[str]] = []
    for s in sessions:
        sid = truncate(s.get("id", ""))
        is_current = s.get("id") == cur_id
        current_marker = "◄ current" if is_current else ""
        cache_read = s.get("cache_read_tokens", 0)
        input_tokens = s.get("input_tokens", 0)
        total_tokens = s.get("total_tokens", 0)
        cache_hit_rate = None
        if cache_read + input_tokens > 0:
            cache_hit_rate = (cache_read / (cache_read + input_tokens)) * 100.0
        rows.append([
            sid,
            s.get("model", ""),
            current_marker,
            fmt_ts(s.get("started_at")),
            fmt_ts(s.get("last_activity_at")),
            fmt_int(s.get("input_tokens", 0)),
            fmt_int(s.get("output_tokens", 0)),
            fmt_int(cache_read),
            fmt_ratio(cache_read, total_tokens),
            fmt_ratio(cache_hit_rate, 100),
            fmt_int(s.get("reasoning_tokens", 0)),
            fmt_int(total_tokens),
            fmt_int(s.get("api_call_count", 0)),
            fmt_cost(s.get("est_cost"), currency),
        ])
    headers = [L("hdr_session"), L("hdr_model"), L("hdr_current"),
               L("hdr_started"), L("hdr_last_activity"), L("hdr_input"),
               L("hdr_output"), L("hdr_cache_read"), L("hdr_cache_multiplier"), L("hdr_cache_hit_rate"),
               L("hdr_reasoning"), L("hdr_total"), L("hdr_api_calls"),
               f"{L('hdr_est_cost')} ({currency})"]
    return box_table(L("session_title"), headers, rows)


def _render_session_models(session_models: list[dict[str, Any]],
                           cfg: dict[str, Any], currency: str) -> str:
    """--session drill-down table: each model/billing-context row."""
    L = lambda k: label(cfg, k)
    session_total = sum(
        int(sm.get("input_tokens", 0) or 0) + int(sm.get("output_tokens", 0) or 0)
        for sm in session_models
    )
    rows: list[list[str]] = []
    for sm in session_models:
        model_total = int(sm.get("input_tokens", 0) or 0) + int(sm.get("output_tokens", 0) or 0)
        cache_read = sm.get("cache_read_tokens", 0)
        input_tokens = sm.get("input_tokens", 0)
        cache_hit_rate = None
        if cache_read + input_tokens > 0:
            cache_hit_rate = (cache_read / (cache_read + input_tokens)) * 100.0
        rows.append([
            sm.get("model", ""),  # full model name, not truncated
            sm.get("billing_provider", "") or L("meta_no_data"),
            truncate(sm.get("billing_base_url", "")),
            sm.get("billing_mode", "") or L("meta_no_data"),
            sm.get("task", "") or L("meta_no_data"),
            fmt_int(sm.get("input_tokens", 0)),
            fmt_int(sm.get("output_tokens", 0)),
            fmt_int(cache_read),
            fmt_ratio(cache_read, model_total),
            fmt_ratio(cache_hit_rate, 100),
            fmt_int(sm.get("cache_write_tokens", 0)),
            fmt_int(sm.get("reasoning_tokens", 0)),
            fmt_int(model_total),
            fmt_share(model_total, session_total),
            fmt_int(sm.get("api_call_count", 0)),
            fmt_cost(sm.get("est_cost"), currency),
            fmt_cost(sm.get("actual_cost"), currency),
            fmt_ts(sm.get("first_seen")),
            fmt_ts(sm.get("last_seen")),
        ])
    headers = [L("hdr_model"), L("hdr_billing_provider"), L("hdr_billing_base_url"),
               L("hdr_billing_mode"), L("hdr_task"), L("hdr_input"), L("hdr_output"),
               L("hdr_cache_read"), L("hdr_cache_multiplier"), L("hdr_cache_hit_rate"),
               L("hdr_cache_write"), L("hdr_reasoning"), L("hdr_total"), L("hdr_share"), L("hdr_api_calls"),
               f"{L('hdr_est_cost')} ({currency})",
               f"{L('hdr_actual_cost')} ({currency})",
               L("hdr_first_seen"), L("hdr_last_seen")]
    return box_table(L("session_title"), headers, rows)


def _render_meta(cfg: dict[str, Any], db_path: str, window: str,
                 profile: Optional[str], fmt: str,
                 current_session: Optional[dict[str, Any]] = None) -> str:
    L = lambda k: label(cfg, k)
    win_label = {
        "lifetime": L("meta_window_lifetime"),
        "7d": L("meta_window_7d"),
        "30d": L("meta_window_30d"),
        "90d": L("meta_window_90d"),
    }.get(window, window)
    rows = [
        [L("hdr_db"), db_path],
        [L("hdr_window"), win_label],
        [L("hdr_profile"), profile or L("meta_no_data")],
        [L("hdr_format"), fmt],
    ]
    if current_session is not None:
        rows.append([
            L("hdr_current_session"),
            f"{truncate(current_session.get('id', ''))} "
            f"({current_session.get('model', '') or L('meta_no_data')})",
        ])
    return box_table(None, ["Key", "Value"], rows)


def _render_timeline(buckets: list[dict[str, Any]], granularity: str,
                     cfg: dict[str, Any], currency: str) -> str:
    """Simple ASCII bar chart of token usage by time bucket."""
    L = lambda k: label(cfg, k)
    if not buckets:
        return f"{L('timeline_title')}\n\n{L('meta_no_data')}"

    max_total = max(int(b.get("total_tokens", 0)) for b in buckets) or 1
    bar_width = 40

    lines: list[str] = []
    lines.append(L("timeline_title"))
    lines.append(f"{L('meta_window')} ({granularity})")
    lines.append("")

    for b in buckets:
        total = int(b.get("total_tokens", 0))
        filled = int((total / max_total) * bar_width) if max_total else 0
        bar = "█" * filled + "░" * (bar_width - filled)
        cache_read = b.get("cache_read_tokens", 0)
        input_tokens = b.get("input_tokens", 0)
        cache_hit_rate = None
        if cache_read + input_tokens > 0:
            cache_hit_rate = (cache_read / (cache_read + input_tokens)) * 100.0
        lines.append(
            f"{str(b.get('bucket', '')):16} │{bar}│ "
            f"{fmt_int(total)} "
            f"({int(b.get('sessions', 0))} {L('meta_sessions')}, "
            f"{fmt_cost(b.get('est_cost', 0), currency)})"
        )
        lines.append(
            f"{'':16}   Cache Multiplier: {fmt_ratio(cache_read, total)}  "
            f"Cache Hit Rate: {fmt_ratio(cache_hit_rate, 100)}"
        )

    return "\n".join(lines)


# -- Top-level renderers ----------------------------------------------------

import shutil

def render_text(totals: dict[str, Any], models: list[dict[str, Any]],
                sessions: list[dict[str, Any]], cfg: dict[str, Any],
                db_path: str, window: str, profile: Optional[str],
                fmt: str, currency: str,
                session_mode: bool = False,
                session_info: Optional[dict[str, Any]] = None,
                session_models: Optional[list[dict[str, Any]]] = None,
                current_session: Optional[dict[str, Any]] = None,
                timeline_mode: bool = False,
                timeline_granularity: str = "day",
                timeline_buckets: Optional[list[dict[str, Any]]] = None
                ) -> str:
    """Build the full plain-text report."""
    parts: list[str] = []
    grand_total = int(totals.get("total_tokens", 0))
    
    # Detect terminal width for responsive tables
    try:
        term_width = shutil.get_terminal_size().columns
    except Exception:
        term_width = 120
    
    # Color support (TTY + NO_COLOR)
    color = Color()
    
    parts.append(_render_meta(cfg, db_path, window, profile, fmt,
                              current_session=current_session))
    parts.append("")

    if timeline_mode:
        parts.append(_render_timeline(
            timeline_buckets or [], timeline_granularity, cfg, currency))
        return "\n".join(parts)

    if session_mode:
        if session_info is not None:
            L = lambda k: label(cfg, k)
            cache_read = totals.get("cache_read_tokens", 0)
            input_tokens = totals.get("input_tokens", 0)
            total_tokens = totals.get("total_tokens", 0)
            cache_hit_rate = None
            if cache_read + input_tokens > 0:
                cache_hit_rate = (cache_read / (cache_read + input_tokens)) * 100.0
            parts.append(box_table(
                L("session_title"), ["Key", "Value"],
                [
                    [L("hdr_session"), truncate(session_info.get("id", ""))],
                    [L("hdr_model"), session_info.get("model", "") or L("meta_no_data")],
                    [L("hdr_started"), fmt_ts(session_info.get("started_at"))],
                    [L("hdr_last_activity"), fmt_ts(session_info.get("last_activity_at"))],
                    [L("hdr_input"), fmt_int(totals.get("input_tokens", 0))],
                    [L("hdr_output"), fmt_int(totals.get("output_tokens", 0))],
                    [L("hdr_cache_read"), fmt_int(cache_read)],
                    [L("hdr_cache_multiplier"), fmt_ratio(cache_read, total_tokens)],
                    [L("hdr_cache_hit_rate"), fmt_ratio(cache_hit_rate, 100)],
                    [L("hdr_cache_write"), fmt_int(totals.get("cache_write_tokens", 0))],
                    [L("hdr_reasoning"), fmt_int(totals.get("reasoning_tokens", 0))],
                    [L("hdr_total"), fmt_int(total_tokens)],
                    [L("hdr_api_calls"), fmt_int(totals.get("api_calls", 0))],
                    [f"{L('hdr_est_cost')} ({currency})",
                     fmt_cost(totals.get("est_cost"), currency)],
                    [f"{L('hdr_actual_cost')} ({currency})",
                     fmt_cost(totals.get("actual_cost"), currency)],
                ],
            ))
            parts.append("")
        if session_models:
            parts.append(_render_session_models(session_models, cfg, currency))
        elif session_info is not None:
            parts.append(label(cfg, "meta_no_data"))
    else:
        # Use new responsive renderers
        parts.append(render_totals_panel(totals, cfg, currency, color))
        parts.append("")
        parts.append(render_models_table(models, grand_total, cfg, currency, color, term_width))
        parts.append("")
        parts.append(render_sessions_table(sessions, current_session, cfg, currency, color, term_width))
    return "\n".join(parts)


def render_json(totals: dict[str, Any], models: list[dict[str, Any]],
                sessions: list[dict[str, Any]], cfg: dict[str, Any],
                db_path: str, window: str, profile: Optional[str],
                fmt: str, currency: str,
                session_mode: bool = False,
                session_info: Optional[dict[str, Any]] = None,
                session_models: Optional[list[dict[str, Any]]] = None,
                current_session: Optional[dict[str, Any]] = None,
                timeline_mode: bool = False,
                timeline_granularity: str = "day",
                timeline_buckets: Optional[list[dict[str, Any]]] = None
                ) -> str:
    out: dict[str, Any] = {
        "db_path": db_path,
        "window": window,
        "profile": profile,
        "format": fmt,
        "currency": currency,
        "totals": totals,
        "models": models,
        "sessions": sessions,
    }
    if session_mode:
        out["session"] = session_info
        out["session_models"] = session_models or []
    if current_session is not None:
        out["current_session"] = current_session
    if timeline_mode:
        out["timeline_granularity"] = timeline_granularity
        out["timeline_buckets"] = timeline_buckets or []
    return json.dumps(out, indent=2, default=str)
