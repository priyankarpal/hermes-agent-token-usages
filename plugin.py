"""Plugin entry point delegate.

Hermes loads this module and calls ``register(ctx)``. Delegates to the
layered ``token_usage.plugin`` implementation.
"""

from token_usage.plugin import register

__all__ = ["register"]
