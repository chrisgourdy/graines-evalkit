"""Adapter port. Any agent — any language, provider or architecture — is reachable through this."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import Field

from evalkit.contracts import AgentResponse, ContractModel, Scenario


class AdapterCapabilities(ContractModel):
    """What the adapter can honestly provide. Drives REPORTED vs ESTIMATED vs UNKNOWN usage."""

    adapter_id: str
    adapter_version: str
    reports_usage: bool = Field(description="Provider returns token usage per call.")
    reports_trajectory: bool = Field(description="Adapter can expose steps/tools/retries.")
    deterministic: bool = Field(description="Same inputs + seed give the same output.")
    supports_seed: bool = False
    supports_timeout: bool = True
    cost_bearing: bool = Field(description="Calls can incur provider charges.")


@runtime_checkable
class AgentAdapter(Protocol):
    """One adapter instance targets one agent version."""

    @property
    def capabilities(self) -> AdapterCapabilities: ...

    @property
    def agent_version(self) -> str: ...

    async def invoke(
        self, scenario: Scenario, *, seed: int | None, timeout_s: float | None
    ) -> AgentResponse:
        """Run the agent on ``scenario.inputs``. Must not raise for agent-level errors:
        return an AgentResponse whose metadata carries ``error``; raise only for adapter faults.
        """
        ...
