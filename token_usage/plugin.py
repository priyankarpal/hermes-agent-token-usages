"""Plugin entry point.

Called by the Hermes plugin loader. Registers the ``tokens`` CLI command;
no TUI/slash command is provided.
"""

from .cli import handle_cli, setup_cli


def register(ctx: object) -> None:
    """Register the ``tokens`` CLI command with Hermes."""
    ctx.register_cli_command(
        name="tokens",
        help="Show token usage analytics from the local Hermes database.",
        description=(
            "Token usage analytics from the local Hermes database "
            "(~/.hermes/state.db) — lifetime totals, per-model and "
            "per-session breakdowns, no network or auth required."
        ),
        setup_fn=setup_cli,
        handler_fn=handle_cli,
    )
