"""token-usage plugin package entry.

Hermes imports this package and calls ``register(ctx)``.
"""

from .plugin import register

__all__ = ["register"]
