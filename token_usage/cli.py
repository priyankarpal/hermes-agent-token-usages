"""CLI: argument parsing + handler + backward-compatible run().

Wires together config, service, and renderers. Thin presentation boundary.
"""

from __future__ import annotations

import argparse
import sqlite3
from typing import Any, Optional

from .config import WINDOWS, FORMATS, cfg_val, label, load_config
from .db import open_db
from .render import render_json, render_text
from .service import TokenUsageService, run_service


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
    parser.add_argument("--timeline", choices=("hour", "day", "month"),
                        default=None,
                        help="Show usage timeline grouped by hour/day/month "
                             "with a simple bar chart.")
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
    parser.add_argument("--timeline", choices=("hour", "day", "month"),
                        default=None,
                        help="Show usage timeline grouped by hour/day/month "
                             "with a simple bar chart.")


def handle_cli(args: argparse.Namespace) -> int | None:
    """CLI handler for ``hermes tokens``. Prints output directly."""
    cfg = _cfg()
    db_path = str(cfg_val(cfg, "db_path", "~/.hermes/state.db"))
    window = str(args.window or cfg_val(cfg, "default_window", "lifetime"))
    fmt = str(args.format or cfg_val(cfg, "output_format", "table"))
    currency = str(cfg_val(cfg, "currency_label", "USD"))
    max_sessions = int(cfg_val(cfg, "max_sessions", 50))
    profile = args.profile or cfg_val(cfg, "profile", None) or None
    include_archived = bool(cfg_val(cfg, "include_archived", False))

    conn = open_db(db_path)
    try:
        service = TokenUsageService(conn, cfg)
        report = service.build_report(args)

        out = (
            render_json(
                report.totals, report.models, report.sessions, cfg, db_path,
                window, profile, fmt, currency,
                session_mode=report.session_mode,
                session_info=report.session_info,
                session_models=report.session_models,
                current_session=report.current_session,
                timeline_mode=report.timeline_mode,
                timeline_granularity=report.timeline_granularity,
                timeline_buckets=report.timeline_buckets,
            )
            if fmt == "json"
            else render_text(
                report.totals, report.models, report.sessions, cfg, db_path,
                window, profile, fmt, currency,
                session_mode=report.session_mode,
                session_info=report.session_info,
                session_models=report.session_models,
                current_session=report.current_session,
                timeline_mode=report.timeline_mode,
                timeline_granularity=report.timeline_granularity,
                timeline_buckets=report.timeline_buckets,
            )
        )
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
