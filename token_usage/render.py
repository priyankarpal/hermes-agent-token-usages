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


# -- Renderers --------------------------------------------------------------

def _render_totals(totals: dict[str, Any], cfg: dict[str, Any],
                   currency: str) -> str:
    L = lambda k: label(cfg, k)
    rows = [
        [L("hdr_sessions"), fmt_int(totals.get("sessions", 0))],
        [L("hdr_input"), fmt_int(totals.get("input_tokens", 0))],
        [L("hdr_output"), fmt_int(totals.get("output_tokens", 0))],
        [L("hdr_cache_read"), fmt_int(totals.get("cache_read_tokens", 0))],
        [L("hdr_cache_write"), fmt_int(totals.get("cache_write_tokens", 0))],
        [L("hdr_reasoning"), fmt_int(totals.get("reasoning_tokens", 0))],
        [L("hdr_total"), fmt_int(totals.get("total_tokens", 0))],
        [L("hdr_api_calls"), fmt_int(totals.get("api_calls", 0))],
        [f"{L('hdr_est_cost')} ({currency})", fmt_cost(totals.get("est_cost", 0), currency)],
        [f"{L('hdr_actual_cost')} ({currency})", fmt_cost(totals.get("actual_cost", 0), currency)],
    ]
    return box_table(L("totals_title"), [L("hdr_sessions"), "Value"], rows)


def _render_models(models: list[dict[str, Any]], grand_total: int,
                   cfg: dict[str, Any], currency: str) -> str:
    L = lambda k: label(cfg, k)
    rows: list[list[str]] = []
    for m in models:
        rows.append([
            truncate(m.get("model", "")),
            fmt_int(m.get("sessions", 0)),
            fmt_int(m.get("input_tokens", 0)),
            fmt_int(m.get("output_tokens", 0)),
            fmt_int(m.get("cache_read_tokens", 0)),
            fmt_int(m.get("total_tokens", 0)),
            fmt_share(m.get("total_tokens", 0), grand_total),
            fmt_int(m.get("api_calls", 0)),
            fmt_cost(m.get("est_cost", 0), currency),
        ])
    headers = [L("hdr_model"), L("hdr_sessions"), L("hdr_input"), L("hdr_output"),
               L("hdr_cache_read"), L("hdr_total"), L("hdr_share"),
               L("hdr_api_calls"), f"{L('hdr_est_cost')} ({currency})"]
    return box_table(L("model_title"), headers, rows)


def _render_sessions(sessions: list[dict[str, Any]], cfg: dict[str, Any],
                     currency: str) -> str:
    L = lambda k: label(cfg, k)
    rows: list[list[str]] = []
    for s in sessions:
        rows.append([
            truncate(s.get("id", "")),
            truncate(s.get("model", "")),
            fmt_ts(s.get("started_at")),
            fmt_ts(s.get("last_activity_at")),
            fmt_int(s.get("input_tokens", 0)),
            fmt_int(s.get("output_tokens", 0)),
            fmt_int(s.get("cache_read_tokens", 0)),
            fmt_int(s.get("reasoning_tokens", 0)),
            fmt_int(s.get("total_tokens", 0)),
            fmt_int(s.get("api_call_count", 0)),
            fmt_cost(s.get("estimated_cost_usd", 0), currency),
        ])
    headers = [L("hdr_session"), L("hdr_model"), L("hdr_started"),
               L("hdr_last_activity"), L("hdr_input"), L("hdr_output"),
               L("hdr_cache_read"), L("hdr_reasoning"), L("hdr_total"),
               L("hdr_api_calls"), f"{L('hdr_est_cost')} ({currency})"]
    return box_table(L("session_title"), headers, rows)


def _render_session_models(session_models: list[dict[str, Any]],
                           cfg: dict[str, Any], currency: str) -> str:
    """--session drill-down table: each model/billing-context row."""
    L = lambda k: label(cfg, k)
    rows: list[list[str]] = []
    for sm in session_models:
        rows.append([
            truncate(sm.get("model", "")),
            sm.get("billing_provider", "") or L("meta_no_data"),
            truncate(sm.get("billing_base_url", "")),
            sm.get("billing_mode", "") or L("meta_no_data"),
            sm.get("task", "") or L("meta_no_data"),
            fmt_int(sm.get("input_tokens", 0)),
            fmt_int(sm.get("output_tokens", 0)),
            fmt_int(sm.get("cache_read_tokens", 0)),
            fmt_int(sm.get("cache_write_tokens", 0)),
            fmt_int(sm.get("reasoning_tokens", 0)),
            fmt_int(sm.get("input_tokens", 0) + sm.get("output_tokens", 0)),
            fmt_int(sm.get("api_call_count", 0)),
            fmt_cost(sm.get("estimated_cost_usd", 0), currency),
            fmt_cost(sm.get("actual_cost_usd", 0), currency),
            fmt_ts(sm.get("first_seen")),
            fmt_ts(sm.get("last_seen")),
        ])
    headers = [L("hdr_model"), L("hdr_billing_provider"), L("hdr_billing_base_url"),
               L("hdr_billing_mode"), L("hdr_task"), L("hdr_input"), L("hdr_output"),
               L("hdr_cache_read"), L("hdr_cache_write"), L("hdr_reasoning"),
               L("hdr_total"), L("hdr_api_calls"),
               f"{L('hdr_est_cost')} ({currency})",
               f"{L('hdr_actual_cost')} ({currency})",
               L("hdr_first_seen"), L("hdr_last_seen")]
    return box_table(L("session_title"), headers, rows)


def _render_meta(cfg: dict[str, Any], db_path: str, window: str,
                 profile: Optional[str], fmt: str) -> str:
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
    return box_table(None, ["Key", "Value"], rows)


def render_text(totals: dict[str, Any], models: list[dict[str, Any]],
                sessions: list[dict[str, Any]], cfg: dict[str, Any],
                db_path: str, window: str, profile: Optional[str],
                fmt: str, currency: str,
                session_mode: bool = False,
                session_info: Optional[dict[str, Any]] = None,
                session_models: Optional[list[dict[str, Any]]] = None) -> str:
    """Build the full plain-text report."""
    parts: list[str] = []
    grand_total = int(totals.get("total_tokens", 0))
    parts.append(_render_meta(cfg, db_path, window, profile, fmt))
    parts.append("")
    if session_mode:
        if session_info is not None:
            L = lambda k: label(cfg, k)
            parts.append(box_table(
                L("session_title"), ["Key", "Value"],
                [
                    [L("hdr_session"), truncate(session_info.get("id", ""))],
                    [L("hdr_model"), session_info.get("model", "") or L("meta_no_data")],
                    [L("hdr_started"), fmt_ts(session_info.get("started_at"))],
                    [L("hdr_last_activity"), fmt_ts(session_info.get("last_activity_at"))],
                    [L("hdr_input"), fmt_int(totals.get("input_tokens", 0))],
                    [L("hdr_output"), fmt_int(totals.get("output_tokens", 0))],
                    [L("hdr_cache_read"), fmt_int(totals.get("cache_read_tokens", 0))],
                    [L("hdr_cache_write"), fmt_int(totals.get("cache_write_tokens", 0))],
                    [L("hdr_reasoning"), fmt_int(totals.get("reasoning_tokens", 0))],
                    [L("hdr_total"), fmt_int(totals.get("total_tokens", 0))],
                    [L("hdr_api_calls"), fmt_int(totals.get("api_calls", 0))],
                    [f"{L('hdr_est_cost')} ({currency})",
                     fmt_cost(totals.get("est_cost", 0), currency)],
                    [f"{L('hdr_actual_cost')} ({currency})",
                     fmt_cost(totals.get("actual_cost", 0), currency)],
                ],
            ))
            parts.append("")
        if session_models:
            parts.append(_render_session_models(session_models, cfg, currency))
        elif session_info is not None:
            parts.append(label(cfg, "meta_no_data"))
    else:
        parts.append(_render_totals(totals, cfg, currency))
        parts.append("")
        parts.append(_render_models(models, grand_total, cfg, currency))
        parts.append("")
        parts.append(_render_sessions(sessions, cfg, currency))
    return "\n".join(parts)


def render_json(totals: dict[str, Any], models: list[dict[str, Any]],
                sessions: list[dict[str, Any]], cfg: dict[str, Any],
                db_path: str, window: str, profile: Optional[str],
                fmt: str, currency: str,
                session_mode: bool = False,
                session_info: Optional[dict[str, Any]] = None,
                session_models: Optional[list[dict[str, Any]]] = None) -> str:
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
    return json.dumps(out, indent=2, default=str)
