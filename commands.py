"""Command handlers for the token-usage plugin CLI."""

from __future__ import annotations

import argparse
from typing import Any, Optional

from .cli import build_arg_parser
from .config import load_config
from .run import run

_cfg_cache: Optional[dict[str, Any]] = None


def _cfg() -> dict[str, Any]:
    global _cfg_cache
    if _cfg_cache is None:
        _cfg_cache = load_config()
    return _cfg_cache


def setup_cli(parser: argparse.ArgumentParser) -> None:
    """Setup function for ``register_cli_command`` — adds argparse arguments."""
    build_arg_parser()._actions  # keep parser intact; add arguments below
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


def handle_cli(args: argparse.Namespace) -> int | None:
    """CLI handler for ``hermes tokens``. Prints output directly."""
    out = run(args, _cfg())
    if out:
        print(out)
    return None
