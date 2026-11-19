"""Hermes Token Usage plugin — local SQLite token analytics.

Surfaces token usage from ~/.hermes/state.db in the CLI with no network,
no auth, and no Hermes Desktop. Every user-facing string is config-driven
(token_plugin.* in ~/.hermes/config.yaml, or TOKEN_PLUGIN_* environment
variables); there are no hardcoded UI strings in this module.

Registration:
  * CLI command  hermes tokens -> handler prints output directly
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

try:
    import yaml  # Hermes runtime dependency
except Exception:  # pragma: no cover - stdlib fallback only
    yaml = None


# ── config keys (the only hardcoded names; all UI text is config-driven) ─

CONFIG_SECTION = "token_plugin"
ENV_PREFIX = "TOKEN_PLUGIN_"
WINDOWS = ("lifetime", "7d", "30d", "90d")
FORMATS = ("table", "json")


# ═════════════════════════════════════════════════════════════════════════
# Config loading
# ═════════════════════════════════════════════════════════════════════════


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def _config_file() -> Path:
    return _hermes_home() / "config.yaml"


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    return _naive_yaml(text)


def _naive_yaml(text: str) -> dict[str, Any]:
    """Tiny indentation-based YAML subset parser (2-3 levels).

    Handles the flat/nested config we need (``token_plugin:`` → ``labels:`` →
    ``hdr_db: ...``) without PyYAML. Lines are grouped by indentation depth.
    """
    data: dict[str, Any] = {}
    # stack of (indent, dict) for open mappings
    stack: list[tuple[int, dict[str, Any]]] = [(-1, data)]

    def _set_parent(indent: int, key: str, val: Any) -> dict[str, Any]:
        # pop to the correct parent depth
        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        parent[key] = val
        return parent

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()
        # pop stack entries deeper or equal to this indent
        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if val == "":
            # open a new mapping at this indent
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = val.strip('"').strip("'")
    return data


def _coerce_env(value: str) -> Any:
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _set_nested(data: dict[str, Any], keys: list[str], value: Any) -> None:
    for k in keys[:-1]:
        data = data.setdefault(k, {})
    data[keys[-1]] = value


def _get_nested(data: Any, keys: list[str], default: Any = None) -> Any:
    cur: Any = data
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def load_config() -> dict[str, Any]:
    """token_plugin config: config.yaml values overlaid by TOKEN_PLUGIN_* env vars."""
    raw = _load_yaml_file(_config_file())
    tp = _get_nested(raw, [CONFIG_SECTION], {}) or {}
    if not isinstance(tp, dict):
        tp = {}
    cfg: dict[str, Any] = {CONFIG_SECTION: dict(tp)}
    for env_key, value in os.environ.items():
        if not env_key.startswith(ENV_PREFIX):
            continue
        suffix = env_key[len(ENV_PREFIX):]
        if suffix:
            _set_nested(cfg, [CONFIG_SECTION, suffix.lower()], _coerce_env(value))
    return cfg


def label(cfg: dict[str, Any], key: str) -> str:
    """User-facing label from config; falls back to the key itself (no hardcoded UI strings)."""
    val = _get_nested(cfg, [CONFIG_SECTION, "labels", key], None)
    return val if val is not None else key


def cfg_val(cfg: dict[str, Any], key: str, default: Any = None) -> Any:
    return _get_nested(cfg, [CONFIG_SECTION, key], default)


# ═════════════════════════════════════════════════════════════════════════
# Database
# ═════════════════════════════════════════════════════════════════════════


def open_db(db_path: str) -> sqlite3.Connection:
    """Open state.db read-only (uri mode=ro) so the running gateway is never locked."""
    expanded = os.path.expanduser(db_path)
    uri = f"file:{expanded}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ═════════════════════════════════════════════════════════════════════════
# Query building
# ═════════════════════════════════════════════════════════════════════════


def _window_offset(window: str) -> Optional[str]:
    return {"7d": "-7 days", "30d": "-30 days", "90d": "-90 days"}.get(window)


def build_where(window: str, include_archived: bool,
                profile: Optional[str], model: Optional[str],
                session: Optional[str]) -> tuple[str, list[Any]]:
    """Return (WHERE clause, params) for the given filters (sessions table)."""
    clauses: list[str] = []
    params: list[Any] = []

    if window != "lifetime":
        offset = _window_offset(window)
        if offset is None:
            raise ValueError(f"Unknown window: {window!r}")
        clauses.append(f"started_at >= strftime('%s', 'now', '{offset}')")

    if not include_archived:
        clauses.append("archived = 0")

    if profile is not None:
        clauses.append("profile_name = ?")
        params.append(profile)

    if model is not None:
        clauses.append("model = ?")
        params.append(model)

    if session is not None:
        clauses.append("id = ?")
        params.append(session)

    where = " AND ".join(clauses) if clauses else "1=1"
    return where, params


def build_models_where(window: str, include_archived: bool,
                       profile: Optional[str]) -> tuple[str, list[Any]]:
    """Return (WHERE clause, params) for session_model_usage joined with sessions.

    session_model_usage has no started_at/archived/profile_name of its own —
    those live on sessions — so the WHERE clause references the sessions alias
    ``s`` and the caller must JOIN sessions s ON s.id = smu.session_id.
    """
    clauses: list[str] = []
    params: list[Any] = []

    if window != "lifetime":
        offset = _window_offset(window)
        if offset is None:
            raise ValueError(f"Unknown window: {window!r}")
        clauses.append(f"s.started_at >= strftime('%s', 'now', '{offset}')")

    if not include_archived:
        clauses.append("s.archived = 0")

    if profile is not None:
        clauses.append("s.profile_name = ?")
        params.append(profile)

    where = " AND ".join(clauses) if clauses else "1=1"
    return where, params


# ═════════════════════════════════════════════════════════════════════════
# Queries
# ═════════════════════════════════════════════════════════════════════════


def query_totals(conn: sqlite3.Connection, where: str,
                 params: list[Any]) -> dict[str, Any]:
    sql = f"""
    SELECT
        COUNT(*) as sessions,
        COALESCE(SUM(input_tokens), 0) as input_tokens,
        COALESCE(SUM(output_tokens), 0) as output_tokens,
        COALESCE(SUM(cache_read_tokens), 0) as cache_read_tokens,
        COALESCE(SUM(cache_write_tokens), 0) as cache_write_tokens,
        COALESCE(SUM(reasoning_tokens), 0) as reasoning_tokens,
        COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
        COALESCE(SUM(api_call_count), 0) as api_calls,
        COALESCE(SUM(estimated_cost_usd), 0) as est_cost,
        COALESCE(SUM(actual_cost_usd), 0) as actual_cost
    FROM sessions
    WHERE {where}
    """
    row = conn.execute(sql, params).fetchone()
    return dict(row)


def query_models(conn: sqlite3.Connection, where: str,
                 params: list[Any]) -> list[dict[str, Any]]:
    """Per-model breakdown from session_model_usage (FR-2).

    session_model_usage is the authoritative source for per-model billing
    detail (billing_provider, billing_base_url, billing_mode) — sessions lacks
    those. Joined with sessions only for window/archived/profile filters.
    Never combined with sessions aggregates for the same report (no double-count).
    """
    sql = f"""
    SELECT
        smu.model,
        COUNT(DISTINCT smu.session_id) as sessions,
        COALESCE(SUM(smu.input_tokens), 0) as input_tokens,
        COALESCE(SUM(smu.output_tokens), 0) as output_tokens,
        COALESCE(SUM(smu.cache_read_tokens), 0) as cache_read_tokens,
        COALESCE(SUM(smu.cache_write_tokens), 0) as cache_write_tokens,
        COALESCE(SUM(smu.input_tokens + smu.output_tokens), 0) as total_tokens,
        COALESCE(SUM(smu.api_call_count), 0) as api_calls,
        COALESCE(SUM(smu.estimated_cost_usd), 0) as est_cost,
        COALESCE(SUM(smu.actual_cost_usd), 0) as actual_cost
    FROM session_model_usage smu
    JOIN sessions s ON s.id = smu.session_id
    WHERE {where}
    GROUP BY smu.model
    ORDER BY total_tokens DESC
    """
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def query_session_models(conn: sqlite3.Connection,
                         session_id: str) -> list[dict[str, Any]]:
    """--session drill-down: each model/billing-context row within a session.

    Queries session_model_usage WHERE session_id = ? — shows every
    (model, billing_provider, billing_base_url, billing_mode, task) row
    for that session. No window/archived/profile filters (specific session).
    """
    sql = """
    SELECT
        model, billing_provider, billing_base_url, billing_mode, task,
        api_call_count, input_tokens, output_tokens, cache_read_tokens,
        cache_write_tokens, reasoning_tokens, estimated_cost_usd,
        actual_cost_usd, first_seen, last_seen
    FROM session_model_usage
    WHERE session_id = ?
    ORDER BY input_tokens + output_tokens DESC
    """
    return [dict(r) for r in conn.execute(sql, [session_id]).fetchall()]


def query_sessions(conn: sqlite3.Connection, where: str,
                   params: list[Any], limit: int) -> list[dict[str, Any]]:
    sql = f"""
    SELECT
        id, model, started_at, last_activity_at,
        input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
        reasoning_tokens, api_call_count, estimated_cost_usd,
        (input_tokens + output_tokens) as total_tokens
    FROM sessions
    WHERE {where}
    ORDER BY total_tokens DESC
    LIMIT ?
    """
    return [dict(r) for r in conn.execute(sql, params + [limit]).fetchall()]


# ═════════════════════════════════════════════════════════════════════════
# Formatting helpers
# ═════════════════════════════════════════════════════════════════════════


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


# ═════════════════════════════════════════════════════════════════════════
# Table renderer (Unicode box-drawing, plain text)
# ═════════════════════════════════════════════════════════════════════════


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


# ═════════════════════════════════════════════════════════════════════════
# Renderers
# ═════════════════════════════════════════════════════════════════════════


def _render_totals(totals: dict[str, Any], cfg: dict[str, Any],
                   currency: str) -> str:
    L = lambda k: label(cfg, k)
    rows = [
        [L("hdr_sessions"), _fmt_int(totals.get("sessions", 0))],
        [L("hdr_input"), _fmt_int(totals.get("input_tokens", 0))],
        [L("hdr_output"), _fmt_int(totals.get("output_tokens", 0))],
        [L("hdr_cache_read"), _fmt_int(totals.get("cache_read_tokens", 0))],
        [L("hdr_cache_write"), _fmt_int(totals.get("cache_write_tokens", 0))],
        [L("hdr_reasoning"), _fmt_int(totals.get("reasoning_tokens", 0))],
        [L("hdr_total"), _fmt_int(totals.get("total_tokens", 0))],
        [L("hdr_api_calls"), _fmt_int(totals.get("api_calls", 0))],
        [f"{L('hdr_est_cost')} ({currency})", _fmt_cost(totals.get("est_cost", 0), currency)],
        [f"{L('hdr_actual_cost')} ({currency})", _fmt_cost(totals.get("actual_cost", 0), currency)],
    ]
    return _box_table(L("totals_title"), [L("hdr_sessions"), "Value"], rows)


def _render_models(models: list[dict[str, Any]], grand_total: int,
                   cfg: dict[str, Any], currency: str) -> str:
    L = lambda k: label(cfg, k)
    rows: list[list[str]] = []
    for m in models:
        rows.append([
            _truncate(m.get("model", "")),
            _fmt_int(m.get("sessions", 0)),
            _fmt_int(m.get("input_tokens", 0)),
            _fmt_int(m.get("output_tokens", 0)),
            _fmt_int(m.get("cache_read_tokens", 0)),
            _fmt_int(m.get("total_tokens", 0)),
            _fmt_share(m.get("total_tokens", 0), grand_total),
            _fmt_int(m.get("api_calls", 0)),
            _fmt_cost(m.get("est_cost", 0), currency),
        ])
    headers = [L("hdr_model"), L("hdr_sessions"), L("hdr_input"), L("hdr_output"),
               L("hdr_cache_read"), L("hdr_total"), L("hdr_share"),
               L("hdr_api_calls"), f"{L('hdr_est_cost')} ({currency})"]
    return _box_table(L("model_title"), headers, rows)


def _render_sessions(sessions: list[dict[str, Any]], cfg: dict[str, Any],
                     currency: str) -> str:
    L = lambda k: label(cfg, k)
    rows: list[list[str]] = []
    for s in sessions:
        rows.append([
            _truncate(s.get("id", "")),
            _truncate(s.get("model", "")),
            _fmt_ts(s.get("started_at")),
            _fmt_ts(s.get("last_activity_at")),
            _fmt_int(s.get("input_tokens", 0)),
            _fmt_int(s.get("output_tokens", 0)),
            _fmt_int(s.get("cache_read_tokens", 0)),
            _fmt_int(s.get("reasoning_tokens", 0)),
            _fmt_int(s.get("total_tokens", 0)),
            _fmt_int(s.get("api_call_count", 0)),
            _fmt_cost(s.get("estimated_cost_usd", 0), currency),
        ])
    headers = [L("hdr_session"), L("hdr_model"), L("hdr_started"),
               L("hdr_last_activity"), L("hdr_input"), L("hdr_output"),
               L("hdr_cache_read"), L("hdr_reasoning"), L("hdr_total"),
               L("hdr_api_calls"), f"{L('hdr_est_cost')} ({currency})"]
    return _box_table(L("session_title"), headers, rows)


def _render_session_models(session_models: list[dict[str, Any]],
                           cfg: dict[str, Any], currency: str) -> str:
    """--session drill-down table: each model/billing-context row within a session."""
    L = lambda k: label(cfg, k)
    rows: list[list[str]] = []
    for sm in session_models:
        rows.append([
            _truncate(sm.get("model", "")),
            sm.get("billing_provider", "") or L("meta_no_data"),
            _truncate(sm.get("billing_base_url", "")),
            sm.get("billing_mode", "") or L("meta_no_data"),
            sm.get("task", "") or L("meta_no_data"),
            _fmt_int(sm.get("input_tokens", 0)),
            _fmt_int(sm.get("output_tokens", 0)),
            _fmt_int(sm.get("cache_read_tokens", 0)),
            _fmt_int(sm.get("cache_write_tokens", 0)),
            _fmt_int(sm.get("reasoning_tokens", 0)),
            _fmt_int(sm.get("input_tokens", 0) + sm.get("output_tokens", 0)),
            _fmt_int(sm.get("api_call_count", 0)),
            _fmt_cost(sm.get("estimated_cost_usd", 0), currency),
            _fmt_cost(sm.get("actual_cost_usd", 0), currency),
            _fmt_ts(sm.get("first_seen")),
            _fmt_ts(sm.get("last_seen")),
        ])
    headers = [L("hdr_model"), L("hdr_billing_provider"), L("hdr_billing_base_url"),
               L("hdr_billing_mode"), L("hdr_task"), L("hdr_input"), L("hdr_output"),
               L("hdr_cache_read"), L("hdr_cache_write"), L("hdr_reasoning"),
               L("hdr_total"), L("hdr_api_calls"),
               f"{L('hdr_est_cost')} ({currency})",
               f"{L('hdr_actual_cost')} ({currency})",
               L("hdr_first_seen"), L("hdr_last_seen")]
    return _box_table(L("session_title"), headers, rows)


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
    return _box_table(None, ["Key", "Value"], rows)


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
        # Session header + aggregated totals for the session
        if session_info is not None:
            L = lambda k: label(cfg, k)
            parts.append(_box_table(
                L("session_title"),
                ["Key", "Value"],
                [
                    [L("hdr_session"), _truncate(session_info.get("id", ""))],
                    [L("hdr_model"), session_info.get("model", "") or L("meta_no_data")],
                    [L("hdr_started"), _fmt_ts(session_info.get("started_at"))],
                    [L("hdr_last_activity"), _fmt_ts(session_info.get("last_activity_at"))],
                    [L("hdr_input"), _fmt_int(totals.get("input_tokens", 0))],
                    [L("hdr_output"), _fmt_int(totals.get("output_tokens", 0))],
                    [L("hdr_cache_read"), _fmt_int(totals.get("cache_read_tokens", 0))],
                    [L("hdr_cache_write"), _fmt_int(totals.get("cache_write_tokens", 0))],
                    [L("hdr_reasoning"), _fmt_int(totals.get("reasoning_tokens", 0))],
                    [L("hdr_total"), _fmt_int(totals.get("total_tokens", 0))],
                    [L("hdr_api_calls"), _fmt_int(totals.get("api_calls", 0))],
                    [f"{L('hdr_est_cost')} ({currency})", _fmt_cost(totals.get("est_cost", 0), currency)],
                    [f"{L('hdr_actual_cost')} ({currency})", _fmt_cost(totals.get("actual_cost", 0), currency)],
                ],
            ))
            parts.append("")
        # Per-model / per-billing-context rows within the session
        if session_models:
            parts.append(_render_session_models(session_models, cfg, currency))
        elif session_info is not None:
            parts.append(L("meta_no_data"))
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


# ═════════════════════════════════════════════════════════════════════════
# Core logic
# ═════════════════════════════════════════════════════════════════════════


def run(ns: argparse.Namespace, cfg: dict[str, Any]) -> str:
    """Execute the token-usage query and return a formatted report string."""
    db_path = str(cfg_val(cfg, "db_path", "~/.hermes/state.db"))
    window = str(ns.window or cfg_val(cfg, "default_window", "lifetime"))
    if window not in WINDOWS:
        return label(cfg, "err_unknown_window").format(window=window)

    fmt = str(ns.format or cfg_val(cfg, "output_format", "table"))
    if fmt not in FORMATS:
        return label(cfg, "err_unknown_format").format(format=fmt)

    profile = ns.profile or cfg_val(cfg, "profile", None) or None
    include_archived = bool(cfg_val(cfg, "include_archived", False))
    max_sessions = int(cfg_val(cfg, "max_sessions", 50))
    currency = str(cfg_val(cfg, "currency_label", "USD"))
    model = ns.model
    session = ns.session

    try:
        conn = open_db(db_path)
    except sqlite3.Error as exc:
        return label(cfg, "err_db_error").format(error=exc)
    except FileNotFoundError as exc:
        return label(cfg, "err_db_missing").format(db_path=db_path)

    try:
        if session:
            # --session drill-down: session header from sessions, model/billing
            # rows from session_model_usage (FR-3 extended).
            session_info = conn.execute(
                "SELECT id, model, started_at, last_activity_at, "
                "input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, "
                "reasoning_tokens, api_call_count, estimated_cost_usd, actual_cost_usd, "
                "(input_tokens + output_tokens) as total_tokens "
                "FROM sessions WHERE id = ?",
                [session],
            ).fetchone()
            session_info = dict(session_info) if session_info else None

            session_models = query_session_models(conn, session)

            # Aggregate totals from the session's model rows (avoid double-count
            # with sessions table — single source of truth here).
            if session_models:
                totals = {
                    "sessions": 1,
                    "input_tokens": sum(m.get("input_tokens", 0) or 0 for m in session_models),
                    "output_tokens": sum(m.get("output_tokens", 0) or 0 for m in session_models),
                    "cache_read_tokens": sum(m.get("cache_read_tokens", 0) or 0 for m in session_models),
                    "cache_write_tokens": sum(m.get("cache_write_tokens", 0) or 0 for m in session_models),
                    "reasoning_tokens": sum(m.get("reasoning_tokens", 0) or 0 for m in session_models),
                    "total_tokens": sum((m.get("input_tokens", 0) or 0) + (m.get("output_tokens", 0) or 0) for m in session_models),
                    "api_calls": sum(m.get("api_call_count", 0) or 0 for m in session_models),
                    "est_cost": sum(m.get("estimated_cost_usd", 0) or 0 for m in session_models),
                    "actual_cost": sum(m.get("actual_cost_usd", 0) or 0 for m in session_models),
                }
            else:
                totals = {
                    "sessions": 0, "input_tokens": 0, "output_tokens": 0,
                    "cache_read_tokens": 0, "cache_write_tokens": 0,
                    "reasoning_tokens": 0, "total_tokens": 0, "api_calls": 0,
                    "est_cost": 0, "actual_cost": 0,
                }

            models: list[dict[str, Any]] = []
            sessions_list: list[dict[str, Any]] = []

            if fmt == "json":
                return render_json(totals, models, sessions_list, cfg, db_path,
                                   window, profile, fmt, currency,
                                   session_mode=True,
                                   session_info=session_info,
                                   session_models=session_models)
            return render_text(totals, models, sessions_list, cfg, db_path,
                               window, profile, fmt, currency,
                               session_mode=True,
                               session_info=session_info,
                               session_models=session_models)

        # Non-session mode: sessions for FR-1/FR-3, session_model_usage for FR-2.
        where, params = build_where(window, include_archived,
                                    profile, model, None)
        totals = query_totals(conn, where, params)

        # FR-2: per-model from session_model_usage (joined with sessions for filters).
        models_where, models_params = build_models_where(window, include_archived, profile)
        if model is not None:
            if models_where == "1=1":
                models_where = "smu.model = ?"
            else:
                models_where += " AND smu.model = ?"
            models_params = models_params + [model]
        models = query_models(conn, models_where, models_params)

        # FR-3: per-session list from sessions.
        sessions = query_sessions(conn, where, params, max_sessions)

        if fmt == "json":
            return render_json(totals, models, sessions, cfg, db_path,
                               window, profile, fmt, currency)
        return render_text(totals, models, sessions, cfg, db_path,
                           window, profile, fmt, currency)
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════
# CLI argument parsing
# ═════════════════════════════════════════════════════════════════════════


def build_arg_parser(prog: str = "hermes tokens") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Token usage analytics from the local Hermes database.",
    )
    parser.add_argument("--window", choices=WINDOWS, default=None,
                        help="Time window: lifetime, 7d, 30d, 90d.")
    parser.add_argument("--model", default=None,
                        help="Filter to a specific model.")
    parser.add_argument("--session", default=None,
                        help="Filter to a specific session ID.")
    parser.add_argument("--profile", default=None,
                        help="Filter to a specific profile_name.")
    parser.add_argument("--format", choices=FORMATS, default=None,
                        help="Output format: table, json.")
    return parser


def parse_args(argv: list[str]) -> argparse.Namespace:
    return build_arg_parser().parse_args(argv)


# ═════════════════════════════════════════════════════════════════════════
# Command handlers
# ═════════════════════════════════════════════════════════════════════════


_cfg_cache: Optional[dict[str, Any]] = None


def _cfg() -> dict[str, Any]:
    global _cfg_cache
    if _cfg_cache is None:
        _cfg_cache = load_config()
    return _cfg_cache


def setup_cli(parser: argparse.ArgumentParser) -> None:
    """Setup function for ``register_cli_command`` — adds argparse arguments."""
    parser.add_argument("--window", choices=WINDOWS, default=None,
                        help="Time window: lifetime, 7d, 30d, 90d.")
    parser.add_argument("--model", default=None,
                        help="Filter to a specific model.")
    parser.add_argument("--session", default=None,
                        help="Filter to a specific session ID.")
    parser.add_argument("--profile", default=None,
                        help="Filter to a specific profile_name.")
    parser.add_argument("--format", choices=FORMATS, default=None,
                        help="Output format: table, json.")


def handle_cli(args: argparse.Namespace) -> int | None:
    """CLI handler for ``hermes tokens``. Prints output directly."""
    out = run(args, _cfg())
    if out:
        print(out)
    return None


# ═════════════════════════════════════════════════════════════════════════
# Plugin entry point
# ═════════════════════════════════════════════════════════════════════════


def register(ctx: Any) -> None:
    """Plugin entry point — called by the Hermes plugin loader.

    Registers only the CLI command (``hermes tokens``). This plugin is
    CLI-only.
    """
    ctx.register_cli_command(
        name="tokens",
        help="Show token usage analytics from the local Hermes database.",
        description="Token usage analytics from the local Hermes database "
                    "(~/.hermes/state.db) — lifetime totals, per-model and "
                    "per-session breakdowns, no network or auth required.",
        setup_fn=setup_cli,
        handler_fn=handle_cli,
    )
