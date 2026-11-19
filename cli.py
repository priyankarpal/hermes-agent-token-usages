"""CLI argument parsing for the token-usage plugin."""

from __future__ import annotations

import argparse

from .config import FORMATS, WINDOWS


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
