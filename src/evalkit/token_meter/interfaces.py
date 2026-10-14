"""Token meter port: records usage with full attribution, aggregates without double counting."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from evalkit.contracts import ContractModel, Cost, TokenUsage


class UsageAttribution(ContractModel):
    """Where a usage record belongs. Exactly one owner per record (no double attribution)."""

    organization_id: str | None = None
    project_id: str
    agent_id: str | None = None
    agent_version: str | None = None
    campaign_id: str | None = None
    scenario_id: str | None = None
    run_id: str | None = None
    step_index: int | None = None
    call_id: str | None = None
    evaluator_id: str | None = Field(
        default=None, description="Set when the usage belongs to an evaluator, not the agent."
    )
    period: str | None = Field(
        default=None, description="ISO date (YYYY-MM-DD) for period rollups."
    )


class TokenMeter(Protocol):
    def record(
        self, usage: TokenUsage, attribution: UsageAttribution, cost: Cost | None = None
    ) -> str:
        """Persist and return the usage record id."""
        ...

    def aggregate(self, **filters: str) -> dict[str, Any]:
        """Totals by category over matching records with a status that inherits the weakest
        source (REPORTED < ESTIMATED < PARTIAL < UNKNOWN); UNKNOWN records are never summed."""
        ...
