"""EVALKIT — evaluation, observability and continuous-improvement framework for AI agents.

Single canonical engine. Public contracts live in :mod:`evalkit.contracts`.
"""

from evalkit.contracts import CONTRACT_SCHEMA_VERSION

__version__ = "0.1.0.dev0"

__all__ = ["CONTRACT_SCHEMA_VERSION", "__version__"]
