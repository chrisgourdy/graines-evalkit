"""Simulated agents — the backbone of provider-free testing (never a production validation).

``sim.deterministic`` returns a fixed output per scenario; ``sim.stochastic`` is seeded and
injects wrong answers, errors and retries with configurable probabilities. Both report
synthetic usage with ``source=REPORTED`` (they *are* the provider) so the accounting path is
exercised end to end; a ``report_usage=False`` param switches them to UNKNOWN to exercise the
estimation path.
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import Any

from evalkit.adapters.interfaces import AdapterCapabilities
from evalkit.contracts import (
    AgentResponse,
    Scenario,
    StepKind,
    TokenUsage,
    TrajectoryStep,
    UsageSource,
    utcnow,
)

_PROVIDER = "sim"


def _synthetic_usage(model: str, inputs: object, output: object, *, report: bool) -> TokenUsage:
    if not report:
        return TokenUsage(provider=_PROVIDER, model=model, source=UsageSource.UNKNOWN)
    n_in = max(1, len(json.dumps(inputs, default=str)) // 4)
    n_out = max(1, len(json.dumps(output, default=str)) // 4)
    return TokenUsage(
        provider=_PROVIDER,
        model=model,
        source=UsageSource.REPORTED,
        input_tokens=n_in,
        output_tokens=n_out,
        total_tokens=n_in + n_out,
        raw={"synthetic": True},
    )


def _step(
    index: int,
    kind: StepKind,
    state: str,
    action: str,
    *,
    next_state: str | None = None,
    tool_name: str | None = None,
    usage: TokenUsage | None = None,
    error: str | None = None,
    retry_of: int | None = None,
) -> TrajectoryStep:
    now = utcnow()
    return TrajectoryStep(
        index=index,
        kind=kind,
        state=state,
        next_state=next_state,
        action=action,
        tool_name=tool_name,
        started_at=now,
        ended_at=now,
        duration_ms=0.0,
        usage=usage,
        error=error,
        retry_of=retry_of,
    )


class DeterministicSimAdapter:
    """Behaviours: ``reference`` (returns scenario.reference_outputs), ``wrong`` (mutates every
    string value), ``fixed`` (``params.outputs[scenario_id]``), ``error`` (agent-level error)."""

    adapter_id = "sim.deterministic"
    adapter_version = "1.0.0"

    def __init__(self, agent_version: str, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        self._agent_version = agent_version
        self.behavior: str = str(p.get("behavior", "reference"))
        self.outputs: dict[str, object] = dict(p.get("outputs", {}))
        self.report_usage: bool = bool(p.get("report_usage", True))
        self.model = str(p.get("model", "sim-deterministic-1"))
        self.tools: list[str] = list(p.get("tools", []))

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            reports_usage=self.report_usage,
            reports_trajectory=True,
            deterministic=True,
            supports_seed=False,
            cost_bearing=False,
        )

    @property
    def agent_version(self) -> str:
        return self._agent_version

    def _output_for(self, scenario: Scenario) -> object:
        if self.behavior == "fixed":
            return self.outputs.get(scenario.scenario_id, {"text": ""})
        if self.behavior == "wrong":
            return _mutate(scenario.reference_outputs)
        return scenario.reference_outputs

    async def invoke(
        self, scenario: Scenario, *, seed: int | None, timeout_s: float | None
    ) -> AgentResponse:
        if self.behavior == "error":
            return AgentResponse(
                output=None,
                usage=[_synthetic_usage(self.model, scenario.inputs, "", report=self.report_usage)],
                trajectory_steps=[_step(0, StepKind.ERROR, "start", "generate", error="sim error")],
                latency_ms=1.0,
                agent_version=self._agent_version,
                metadata={"error": "simulated agent error"},
            )
        output = self._output_for(scenario)
        usage = _synthetic_usage(self.model, scenario.inputs, output, report=self.report_usage)
        steps = [
            _step(0, StepKind.LLM_CALL, "start", "generate", next_state="answered", usage=usage)
        ]
        for i, tool in enumerate(self.tools, start=1):
            steps.append(_step(i, StepKind.TOOL_CALL, "answered", tool, tool_name=tool))
        steps.append(_step(len(steps), StepKind.TERMINAL, "answered", "done", next_state="done"))
        return AgentResponse(
            output=output,
            usage=[usage],
            trajectory_steps=[s.model_dump(mode="json") for s in steps],
            latency_ms=1.0,
            agent_version=self._agent_version,
        )


class StochasticSimAdapter:
    """Seeded randomness: ``p_wrong``, ``p_error``, ``p_retry`` (retry then succeed),
    ``latency_ms`` (mean) with jitter. Same seed ⇒ same behaviour (tested)."""

    adapter_id = "sim.stochastic"
    adapter_version = "1.0.0"

    def __init__(self, agent_version: str, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        self._agent_version = agent_version
        self.p_wrong = float(p.get("p_wrong", 0.2))
        self.p_error = float(p.get("p_error", 0.05))
        self.p_retry = float(p.get("p_retry", 0.1))
        self.latency_ms = float(p.get("latency_ms", 50.0))
        self.report_usage = bool(p.get("report_usage", True))
        self.model = str(p.get("model", "sim-stochastic-1"))
        self.sleep = bool(p.get("sleep", False))

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            reports_usage=self.report_usage,
            reports_trajectory=True,
            deterministic=False,
            supports_seed=True,
            cost_bearing=False,
        )

    @property
    def agent_version(self) -> str:
        return self._agent_version

    async def invoke(
        self, scenario: Scenario, *, seed: int | None, timeout_s: float | None
    ) -> AgentResponse:
        rng = random.Random(f"{seed}:{scenario.scenario_id}")  # noqa: S311 — simulation only
        steps: list[TrajectoryStep] = []
        usages: list[TokenUsage] = []
        latency = max(1.0, rng.gauss(self.latency_ms, self.latency_ms * 0.2))
        if self.sleep:
            await asyncio.sleep(latency / 1000)
        index = 0
        if rng.random() < self.p_retry:
            u = _synthetic_usage(self.model, scenario.inputs, "", report=self.report_usage)
            usages.append(u)
            steps.append(
                _step(index, StepKind.ERROR, "start", "generate", error="transient", usage=u)
            )
            index += 1
            steps.append(_step(index, StepKind.RETRY, "start", "generate", retry_of=0))
            index += 1
        if rng.random() < self.p_error:
            u = _synthetic_usage(self.model, scenario.inputs, "", report=self.report_usage)
            usages.append(u)
            steps.append(_step(index, StepKind.ERROR, "start", "generate", error="fatal", usage=u))
            return AgentResponse(
                output=None,
                usage=usages,
                trajectory_steps=[s.model_dump(mode="json") for s in steps],
                latency_ms=latency,
                agent_version=self._agent_version,
                metadata={"error": "simulated fatal error"},
            )
        wrong = rng.random() < self.p_wrong
        output = _mutate(scenario.reference_outputs) if wrong else scenario.reference_outputs
        u = _synthetic_usage(self.model, scenario.inputs, output, report=self.report_usage)
        usages.append(u)
        steps.append(
            _step(index, StepKind.LLM_CALL, "start", "generate", next_state="answered", usage=u)
        )
        steps.append(_step(index + 1, StepKind.TERMINAL, "answered", "done", next_state="done"))
        return AgentResponse(
            output=output,
            usage=usages,
            trajectory_steps=[s.model_dump(mode="json") for s in steps],
            latency_ms=latency,
            agent_version=self._agent_version,
            metadata={"wrong": wrong},
        )


def _mutate(value: object) -> object:
    """Deterministically corrupt reference outputs (strings suffixed, numbers +1)."""
    if isinstance(value, dict):
        return {k: _mutate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mutate(v) for v in value]
    if isinstance(value, str):
        return value + " (wrong)"
    if isinstance(value, bool):
        return not value
    if isinstance(value, int | float):
        return value + 1
    return value
