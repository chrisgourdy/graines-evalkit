"""ADAPTERS — bridge between EVALKIT and agents/providers. See docs/ADAPTER_SPEC.md."""

from evalkit.adapters.interfaces import AdapterCapabilities, AgentAdapter
from evalkit.adapters.registry import adapter_ids, create_adapter, register_adapter

__all__ = [
    "AdapterCapabilities",
    "AgentAdapter",
    "adapter_ids",
    "create_adapter",
    "register_adapter",
]
