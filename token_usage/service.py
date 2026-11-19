"""Service layer: builds token-usage reports.

Coordinates DB queries and domain entities into a UsageReport.
Contains no CLI, no rendering, no config parsing beyond reading values.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from .config import WINDOWS, cfg_val
from .db import open_db
from .domain import (
    Currency, ModelUsage, OutputFormat, Session, SessionModelUsageRow,
    TimelineBucket, UsageReport, Window,
)


def _window_offset(window: str) -> Optional[str]:
    return {"7d": "-7 days", "30d": "-30 days", "90d": "-90 days"}.get(window)


def build_where(window: str, include_archived: bool, profile: Optional[str],
                model: Optional[str] = None, session: Optional[str] = None
                ) -> tuple[str, list[Any]]:
    """WHERE clause + params for the sessions table."""
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
    """WHERE clause + params for session_model_usage joined with sessions."""
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


class TokenUsageService:
    def __init__(self, conn: sqlite3.Connection, cfg: dict[str, Any]) -> None:
        self._conn = conn
        self._cfg = cfg

    def build_report(self, ns: Any) -> UsageReport:
        cfg = self._cfg
        db_path = str(cfg_val(cfg, "db_path", "~/.hermes/state.db"))
        window = str(ns.window or cfg_val(cfg, "default_window", "lifetime"))
        if window not in WINDOWS:
            raise ValueError(f"Unknown window: {window!r}")
        fmt = str(ns.format or cfg_val(cfg, "output_format", "table"))
        if fmt not in ("table", "json"):
            raise ValueError(f"Unknown format: {fmt!r}")
        currency = str(cfg_val(cfg, "currency_label", "USD"))
        max_sessions = int(cfg_val(cfg, "max_sessions", 50))
        profile = ns.profile or cfg_val(cfg, "profile", None) or None
        include_archived = bool(cfg_val(cfg, "include_archived", False))
        granularity = str(getattr(ns, "timeline", None) or "day")
        if granularity not in ("hour", "day", "month"):
            granularity = "day"

        meta = {
            "db_path": db_path,
            "window": window,
            "profile": profile,
            "format": fmt,
            "currency": currency,
        }

        # -- timeline mode -------------------------------------------------
        if getattr(ns, "timeline", None):
            where, params = build_where(window, include_archived, profile)
            buckets = self._build_timeline(granularity, where, params)
            totals = self._aggregate_totals(where, params)
            return UsageReport(
                totals=totals, models=[], sessions=[], meta=meta,
                session_mode=False, timeline_mode=True,
                timeline_granularity=granularity,
                timeline_buckets=buckets,
            )

        # -- current session (always included in normal reports) -----------
        current_session = self._get_current_session(include_archived, profile)

        if ns.session:
            return self._build_session_report(
                ns.session, window, include_archived, profile,
                fmt, currency, meta, current_session,
            )

        where, params = build_where(window, include_archived, profile, ns.model, None)
        totals = self._aggregate_totals(where, params)

        models_where, models_params = build_models_where(window, include_archived, profile)
        if ns.model is not None:
            if models_where == "1=1":
                models_where = "smu.model = ?"
            else:
                models_where += " AND smu.model = ?"
            models_params = models_params + [ns.model]
        models = self._list_models(models_where, models_params)
        sessions = self._list_sessions(where, params, max_sessions)

        # mark the current session in the sessions list
        cur_id = current_session.get("id") if current_session else None
        for s in sessions:
            s["is_current"] = (s.get("id") == cur_id)

        return UsageReport(
            totals=totals, models=models, sessions=sessions, meta=meta,
            session_mode=False, current_session=current_session,
        )

    # -- current session ----------------------------------------------------

    def _get_current_session(
        self, include_archived: bool, profile: Optional[str]
    ) -> Optional[dict[str, Any]]:
        """Most recent active session by last_activity_at."""
        clauses: list[str] = []
        params: list[Any] = []
        if not include_archived:
            clauses.append("archived = 0")
        if profile is not None:
            clauses.append("profile_name = ?")
            params.append(profile)
        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"""
        SELECT
            id, model, started_at, last_activity_at,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            reasoning_tokens, api_call_count, estimated_cost_usd,
            actual_cost_usd, (input_tokens + output_tokens) as total_tokens
        FROM sessions
        WHERE {where}
        ORDER BY last_activity_at DESC
        LIMIT 1
        """
        row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    # -- timeline -----------------------------------------------------------

    def _time_bucket_expr(self, granularity: str) -> str:
        if granularity == "hour":
            return "strftime('%Y-%m-%d %H', datetime(started_at, 'unixepoch'))"
        if granularity == "month":
            return "strftime('%Y-%m', datetime(started_at, 'unixepoch'))"
        # day (default)
        return "strftime('%Y-%m-%d', datetime(started_at, 'unixepoch'))"

    def _build_timeline(
        self, granularity: str, where: str, params: list[Any]
    ) -> list[dict[str, Any]]:
        bucket_expr = self._time_bucket_expr(granularity)
        sql = f"""
        SELECT
            {bucket_expr} as bucket,
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
        GROUP BY bucket
        ORDER BY bucket ASC
        """
        return [TimelineBucket.from_row(dict(r)).to_dict()
                for r in self._conn.execute(sql, params).fetchall()]

    # -- internal query helpers -------------------------------------------

    def _aggregate_totals(self, where: str, params: list[Any]) -> dict[str, Any]:
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
        row = self._conn.execute(sql, params).fetchone()
        return dict(row)

    def _list_models(self, where: str, params: list[Any]) -> list[dict[str, Any]]:
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
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def _list_sessions(self, where: str, params: list[Any],
                       limit: int) -> list[dict[str, Any]]:
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
        return [dict(r) for r in self._conn.execute(sql, params + [limit]).fetchall()]

    def _get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        row = self._conn.execute(
            """
            SELECT id, model, started_at, last_activity_at,
                   input_tokens, output_tokens, cache_read_tokens,
                   cache_write_tokens, reasoning_tokens, api_call_count,
                   estimated_cost_usd, actual_cost_usd,
                   (input_tokens + output_tokens) as total_tokens
            FROM sessions WHERE id = ?
            """,
            [session_id],
        ).fetchone()
        return dict(row) if row else None

    def _list_session_models(self, session_id: str) -> list[dict[str, Any]]:
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
        return [dict(r) for r in self._conn.execute(sql, [session_id]).fetchall()]

    # -- session drill-down report ----------------------------------------

    def _build_session_report(self, session_id: str, window: str,
                              include_archived: bool, profile: Optional[str],
                              fmt: str, currency: str,
                              meta: dict[str, Any],
                              current_session: Optional[dict[str, Any]] = None
                              ) -> UsageReport:
        session_info = self._get_session(session_id)
        session_models = self._list_session_models(session_id)

        if session_models:
            totals = {
                "sessions": 1,
                "input_tokens": sum(m.get("input_tokens", 0) or 0 for m in session_models),
                "output_tokens": sum(m.get("output_tokens", 0) or 0 for m in session_models),
                "cache_read_tokens": sum(m.get("cache_read_tokens", 0) or 0 for m in session_models),
                "cache_write_tokens": sum(m.get("cache_write_tokens", 0) or 0 for m in session_models),
                "reasoning_tokens": sum(m.get("reasoning_tokens", 0) or 0 for m in session_models),
                "total_tokens": sum(
                    (m.get("input_tokens", 0) or 0) + (m.get("output_tokens", 0) or 0)
                    for m in session_models
                ),
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

        meta.update({
            "db_path": str(self._cfg and self._cfg.get("db_path", "~/.hermes/state.db")),
            "window": window,
            "profile": profile,
            "format": fmt,
            "currency": currency,
        })

        return UsageReport(
            totals=totals, models=[], sessions=[], meta=meta,
            session_mode=True, session_info=session_info,
            session_models=session_models, current_session=current_session,
        )


def run_service(db_path: str, cfg: dict[str, Any], ns: Any) -> UsageReport:
    """Convenience: open DB, build report, return UsageReport."""
    conn = open_db(db_path)
    try:
        service = TokenUsageService(conn, cfg)
        return service.build_report(ns)
    finally:
        conn.close()
