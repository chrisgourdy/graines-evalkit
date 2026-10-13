"""Budget contract (COST_CONTROLLER). Hierarchy: org > project > agent > campaign.

No universal default budget exists. A missing budget at every level blocks paid runs.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from evalkit.contracts.base import ContractModel


class BudgetScope(StrEnum):
    ORGANIZATION = "organization"
    PROJECT = "project"
    AGENT = "agent"
    CAMPAIGN = "campaign"
    DAY = "day"
    MONTH = "month"
    EVALUATION_TYPE = "evaluation_type"


class BudgetThresholds(ContractModel):
    """Fractions of the cap (0-1). info < warning < 1.0 (blocking)."""

    info: float = Field(default=0.5, ge=0, le=1)
    warning: float = Field(default=0.8, ge=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> BudgetThresholds:
        if self.info > self.warning:
            msg = "info threshold must be <= warning threshold"
            raise ValueError(msg)
        return self


class Budget(ContractModel):
    budget_id: str
    scope: BudgetScope
    scope_ref: str = Field(description="Id of the scoped entity (project_id, campaign_id, ...).")
    max_cost: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    max_tokens: int | None = Field(default=None, ge=0)
    thresholds: BudgetThresholds = Field(default_factory=BudgetThresholds)
    inherits_from: str | None = Field(default=None, description="Parent budget_id.")

    @model_validator(mode="after")
    def _has_cap(self) -> Budget:
        if self.max_cost is None and self.max_tokens is None:
            msg = "a budget needs at least one cap (max_cost or max_tokens)"
            raise ValueError(msg)
        return self
