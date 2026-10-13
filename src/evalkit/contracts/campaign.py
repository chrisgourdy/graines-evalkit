"""Campaign contract — a planned, budgeted set of runs."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from evalkit.contracts.base import ContractModel
from evalkit.contracts.budget import Budget


class Profile(StrEnum):
    QUICK = "QUICK"
    STANDARD = "STANDARD"
    DEEP = "DEEP"
    EXTENDED = "EXTENDED"


class CampaignStatus(StrEnum):
    PLANNED = "PLANNED"
    DRY_RUN = "DRY_RUN"
    RUNNING = "RUNNING"
    SUSPENDED = "SUSPENDED"
    COMPLETED = "COMPLETED"
    STOPPED_BUDGET = "STOPPED_BUDGET"
    STOPPED_ELIMINATORY = "STOPPED_ELIMINATORY"
    FAILED = "FAILED"


class CampaignPlan(ContractModel):
    """Pre-execution forecast (COST_CONTROLLER). Uncertainty is explicit, never hidden."""

    planned_runs: int = Field(ge=0)
    expected_tokens: int | None = None
    expected_agent_cost: float | None = None
    expected_evaluator_cost: float | None = None
    expected_retry_cost: float | None = None
    expected_external_cost: float | None = None
    currency: str = "USD"
    uncertainty: str = Field(description="How the forecast was built and how uncertain it is.")
    basis: str = Field(description="'historical' | 'conservative_default' | 'mixed'.")


class Campaign(ContractModel):
    campaign_id: str
    project_id: str
    agent_id: str
    agent_version: str
    profile: Profile
    scenario_ids: list[str] = Field(min_length=1)
    repetitions_override: int | None = Field(default=None, ge=1)
    seed: int | None = None
    budget: Budget | None = None
    plan: CampaignPlan | None = None
    dry_run: bool = False
    status: CampaignStatus = CampaignStatus.PLANNED
    baseline_campaign_id: str | None = None
    price_snapshot_ids: list[str] = Field(
        default_factory=list, description="PriceEntry ids frozen for this campaign."
    )
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    stop_reason: str | None = None
    evalkit_version: str
