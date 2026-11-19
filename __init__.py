"""token-usage plugin entry point.

Hermes imports ``hermes_plugins.token-usage`` and calls ``register(ctx)``.
"""

from .token_usage import register

__all__ = ["register"]
