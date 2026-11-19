"""SQL query building and execution for the token-usage plugin."""

from __future__ import annotations

from typing import Any, Optional

import sqlite3

from .config import WINDOWS


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
    """Per-model breakdown from session_model_usage.

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
