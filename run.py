"""Core logic for the token-usage plugin."""

from __future__ import annotations

import argparse
import sqlite3
from typing import Any, Optional

from .config import cfg_val, label, load_config
from .db import open_db
from .queries import build_models_where, build_where, query_models, \
    query_session_models, query_sessions, query_totals
from .render import render_json, render_text


def run(ns: argparse.Namespace, cfg: dict[str, Any]) -> str:
    """Execute the token-usage query and return a formatted report string."""
    db_path = str(cfg_val(cfg, "db_path", "~/.hermes/state.db"))
    window = str(ns.window or cfg_val(cfg, "default_window", "lifetime"))
    if window not in ("lifetime", "7d", "30d", "90d"):
        return label(cfg, "err_unknown_window").format(window=window)

    fmt = str(ns.format or cfg_val(cfg, "output_format", "table"))
    if fmt not in ("table", "json"):
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
            # rows from session_model_usage.
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

            # Aggregate totals from the session's model rows (single source of
            # truth; avoids double-counting with the sessions table).
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

        # Non-session mode: sessions for totals/sessions, session_model_usage for models.
        where, params = build_where(window, include_archived,
                                    profile, model, None)
        totals = query_totals(conn, where, params)

        # Per-model from session_model_usage (joined with sessions for filters).
        models_where, models_params = build_models_where(window, include_archived, profile)
        if model is not None:
            if models_where == "1=1":
                models_where = "smu.model = ?"
            else:
                models_where += " AND smu.model = ?"
            models_params = models_params + [model]
        models = query_models(conn, models_where, models_params)

        # Per-session list from sessions.
        sessions = query_sessions(conn, where, params, max_sessions)

        if fmt == "json":
            return render_json(totals, models, sessions, cfg, db_path,
                               window, profile, fmt, currency)
        return render_text(totals, models, sessions, cfg, db_path,
                           window, profile, fmt, currency)
    finally:
        conn.close()
