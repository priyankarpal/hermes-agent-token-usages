"""CLI: argument parsing + handler + backward-compatible run().

Wires together config, service, and renderers. Thin presentation boundary.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from typing import Any, Optional

from .config import WINDOWS, FORMATS, cfg_val, label, load_config
from .db import open_db
from .render import render_json, render_text
from .service import TokenUsageService, run_service, build_models_where


_cfg_cache: Optional[dict[str, Any]] = None


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
    parser.add_argument("--by", choices=("day", "month", "year"),
                        default="day",
                        help="Show usage timeline: day (heatmap), month, or year (bar charts).")
    parser.add_argument("--page", type=int, default=1,
                        help="Page number for sessions table (default: 1).")
    parser.add_argument("--page-size", type=int, default=10,
                        help="Rows per page for sessions table (default: 10).")
    parser.add_argument("--width", type=int, default=None,
                        help="Terminal width override (default: auto-detect, min 60).")
    return parser


def parse_args(argv: list[str]) -> argparse.Namespace:
    return build_arg_parser().parse_args(argv)


def _cfg() -> dict[str, Any]:
    global _cfg_cache
    if _cfg_cache is None:
        _cfg_cache = load_config()
    return _cfg_cache


def setup_cli(parser: argparse.ArgumentParser) -> None:
    """Setup function for ``register_cli_command`` — adds argparse arguments."""
    parser.add_argument("--window", choices=("lifetime", "7d", "30d", "90d"), default=None,
                        help="Time window: lifetime, 7d, 30d, 90d.")
    parser.add_argument("--model", default=None,
                        help="Filter to a specific model.")
    parser.add_argument("--session", default=None,
                        help="Filter to a specific session ID.")
    parser.add_argument("--profile", default=None,
                        help="Filter to a specific profile_name.")
    parser.add_argument("--format", choices=("table", "json"), default=None,
                        help="Output format: table, json.")
    parser.add_argument("--by", choices=("day", "month", "year"),
                        default="day",
                        help="Show usage timeline: day (heatmap), month, or year (bar charts).")
    parser.add_argument("--page", type=int, default=1,
                        help="Page number for sessions table (default: 1).")
    parser.add_argument("--page-size", type=int, default=10,
                        help="Rows per page for sessions table (default: 10).")
    parser.add_argument("--width", type=int, default=None,
                        help="Terminal width override (default: auto-detect, min 60).")


def handle_cli(args: argparse.Namespace) -> int | None:
    """CLI handler for ``hermes tokens``. Prints output directly."""
    # Validate arguments
    if args.page < 1:
        print("page must be >= 1", file=sys.stderr)
        return 2
    if args.page_size < 1:
        print("page-size must be >= 1", file=sys.stderr)
        return 2
    if args.width is not None and args.width < 60:
        print("width must be >= 60", file=sys.stderr)
        return 2

    cfg = _cfg()
    db_path = str(cfg_val(cfg, "db_path", "~/.hermes/state.db"))
    window = str(args.window or cfg_val(cfg, "default_window", "lifetime"))
    fmt = str(args.format or cfg_val(cfg, "output_format", "table"))
    currency = str(cfg_val(cfg, "currency_label", "USD"))
    max_sessions = int(cfg_val(cfg, "max_sessions", 50))
    profile = args.profile or cfg_val(cfg, "profile", None) or None
    include_archived = bool(cfg_val(cfg, "include_archived", False))

    # Use --by for timeline granularity (default: day) - always show in regular report
    timeline_granularity = args.by if args.by else "day"

    conn = open_db(db_path)
    try:
        service = TokenUsageService(conn, cfg)
        # Build a modified args object with timeline info
        class ArgsProxy:
            def __init__(self, args, timeline_granularity):
                self.window = args.window
                self.model = args.model
                self.session = args.session
                self.profile = args.profile
                self.format = args.format
                self.timeline_granularity = timeline_granularity
                # Disable timeline_mode in service - we want full report with timeline
                self.timeline = False

        proxy_args = ArgsProxy(args, timeline_granularity)
        report = service.build_report(proxy_args)

        # Fetch timeline buckets separately
        where, params = build_models_where(window, include_archived, profile)
        timeline_buckets = service._build_timeline(timeline_granularity, where, params)

        try:
            out = (
                render_json(
                    report.totals, report.models, report.sessions, cfg, db_path,
                    window, profile, fmt, currency,
                    session_mode=report.session_mode,
                    session_info=report.session_info,
                    session_models=report.session_models,
                    current_session=report.current_session,
                    timeline_mode=report.timeline_mode,
                    timeline_granularity=timeline_granularity,
                    timeline_buckets=timeline_buckets,
                )
                if fmt == "json"
                else render_text(
                    report.totals, report.models, report.sessions, cfg, db_path,
                    window, profile, fmt, currency,
                    session_mode=report.session_mode,
                    session_info=report.session_info,
                    session_models=report.session_models,
                    current_session=report.current_session,
                    timeline_mode=False,  # Never use timeline_mode - timeline is part of regular report
                    timeline_granularity=timeline_granularity,
                    timeline_buckets=timeline_buckets,
                    page=args.page,
                    page_size=args.page_size,
                )
            )
        except ValueError as e:
            if "page out of range" in str(e):
                print("page out of range", file=sys.stderr)
                return 2
            raise
    finally:
        conn.close()

    if out:
        print(out)
    return None


def run(ns: argparse.Namespace, cfg: dict[str, Any]) -> str:
    """Backward-compatible entry: returns a formatted report string."""
    db_path = str(cfg_val(cfg, "db_path", "~/.hermes/state.db"))
    window = str(ns.window or cfg_val(cfg, "default_window", "lifetime"))
    if window not in WINDOWS:
        return label(cfg, "err_unknown_window").format(window=window)
    fmt = str(ns.format or cfg_val(cfg, "output_format", "table"))
    if fmt not in FORMATS:
        return label(cfg, "err_unknown_format").format(format=fmt)
    try:
        report = run_service(db_path, cfg, ns)
    except sqlite3.Error as exc:
        return label(cfg, "err_db_error").format(error=exc)
    except FileNotFoundError as exc:
        return label(cfg, "err_db_missing").format(db_path=db_path)
    currency = str(cfg_val(cfg, "currency_label", "USD"))
    profile_val = ns.profile or cfg_val(cfg, "profile", None) or None
    if fmt == "json":
        return render_json(
            report.totals, report.models, report.sessions, cfg, db_path,
            window, profile_val, fmt, currency,
            session_mode=report.session_mode,
            session_info=report.session_info,
            session_models=report.session_models,
            current_session=report.current_session,
            timeline_mode=report.timeline_mode,
            timeline_granularity=report.timeline_granularity,
            timeline_buckets=report.timeline_buckets,
        )
    return render_text(
        report.totals, report.models, report.sessions, cfg, db_path,
        window, profile_val, fmt, currency,
        session_mode=report.session_mode,
        session_info=report.session_info,
        session_models=report.session_models,
        current_session=report.current_session,
        timeline_mode=report.timeline_mode,
        timeline_granularity=report.timeline_granularity,
        timeline_buckets=report.timeline_buckets,
    )
