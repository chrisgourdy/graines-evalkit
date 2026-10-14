"""``python.callable`` — wrap an in-process callable ``fn(inputs: dict, context: dict) -> object``.

Usage is UNKNOWN unless the callable returns a ``(output, usage_list)`` tuple.
"""

from __future__ import annotations

import importlib
import inspect
import time
from collections.abc import Callable
from typing import Any

from evalkit.adapters.interfaces import AdapterCapabilities
from evalkit.contracts import AgentResponse, Scenario, TokenUsage, UsageSource


class CallableAdapter:
    adapter_id = "python.callable"
    adapter_version = "1.0.0"

    def __init__(self, agent_version: str, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        self._agent_version = agent_version
        target = p.get("target")
        fn = p.get("fn")
        if fn is None and isinstance(target, str):
            module_name, _, attr = target.rpartition(":")
            fn = getattr(importlib.import_module(module_name), attr)
        if not callable(fn):
            msg = "python.callable needs params.target ('module:function') or params.fn"
            raise ValueError(msg)
        self.fn: Callable[..., Any] = fn
        self.cost_bearing = bool(p.get("cost_bearing", False))
        self.model = str(p.get("model", "unknown"))
        self.provider = str(p.get("provider", "callable"))

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            reports_usage=False,
            reports_trajectory=False,
            deterministic=False,
            supports_seed=False,
            cost_bearing=self.cost_bearing,
        )

    @property
    def agent_version(self) -> str:
        return self._agent_version

    async def invoke(
        self, scenario: Scenario, *, seed: int | None, timeout_s: float | None
    ) -> AgentResponse:
        start = time.perf_counter()
        try:
            result = self.fn(scenario.inputs, scenario.context)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:  # agent-level failure, returned not raised
            return AgentResponse(
                output=None,
                usage=[
                    TokenUsage(provider=self.provider, model=self.model, source=UsageSource.UNKNOWN)
                ],
                latency_ms=(time.perf_counter() - start) * 1000,
                agent_version=self._agent_version,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )
        latency = (time.perf_counter() - start) * 1000
        usage: list[TokenUsage]
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], list):
            output, usage = result[0], [TokenUsage.model_validate(u) for u in result[1]]
        else:
            output = result
            usage = [
                TokenUsage(provider=self.provider, model=self.model, source=UsageSource.UNKNOWN)
            ]
        return AgentResponse(
            output=output, usage=usage, latency_ms=latency, agent_version=self._agent_version
        )
