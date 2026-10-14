"""Adapter registry: adapter id → factory(agent_version, params)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evalkit.adapters.callable_adapter import CallableAdapter
from evalkit.adapters.interfaces import AgentAdapter
from evalkit.adapters.sim import DeterministicSimAdapter, StochasticSimAdapter

AdapterFactory = Callable[[str, dict[str, Any]], AgentAdapter]

_REGISTRY: dict[str, AdapterFactory] = {
    "sim.deterministic": DeterministicSimAdapter,
    "sim.stochastic": StochasticSimAdapter,
    "python.callable": CallableAdapter,
}


def register_adapter(adapter_id: str, factory: AdapterFactory) -> None:
    _REGISTRY[adapter_id] = factory


def create_adapter(adapter_id: str, agent_version: str, params: dict[str, Any]) -> AgentAdapter:
    try:
        factory = _REGISTRY[adapter_id]
    except KeyError as exc:
        msg = f"unknown adapter {adapter_id!r}; known: {sorted(_REGISTRY)}"
        raise KeyError(msg) from exc
    return factory(agent_version, params)


def adapter_ids() -> list[str]:
    return sorted(_REGISTRY)
