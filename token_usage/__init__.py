"""token-usage plugin package.

Hermes imports ``token_usage`` and calls ``register(ctx)``.
"""

from .plugin import register

__all__ = ["register"]
