"""Cost controller port. Enforced by code, independent from any LLM instruction."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from evalkit.contracts import Campaign, CampaignPlan, ContractModel, Cost


class BudgetDecision(StrEnum):
    ALLOW = "ALLOW"
    ALLOW_WITH_WARNING = "ALLOW_WITH_WARNING"
    BLOCK = "BLOCK"


class Reservation(ContractModel):
    reservation_id: str
    budget_id: str
    campaign_id: str
    run_id: str | None = None
    reserved_cost: float
    reserved_tokens: int | None = None
    currency: str
    created_at: datetime
    settled: bool = False
    observed: Cost | None = None


class CostController(Protocol):
    def forecast(
        self,
        campaign: Campaign | None,
        *,
        planned_runs: int,
        cost_bearing: bool,
        history_tokens: list[int] | None = None,
        price_per_million_hint: float | None = None,
        evaluator_runs_cost_bearing: int = 0,
    ) -> CampaignPlan: ...

    def reserve(
        self,
        campaign: Campaign,
        *,
        run_id: str | None,
        expected_cost: float,
        expected_tokens: int | None,
    ) -> tuple[BudgetDecision, Reservation | None]:
        """Atomic check-and-reserve. Safe under concurrent workers (storage-level locking)."""
        ...

    def settle(
        self, reservation_id: str, observed: Cost, observed_tokens: int | None = None
    ) -> None: ...

    def release(self, reservation_id: str) -> None: ...
