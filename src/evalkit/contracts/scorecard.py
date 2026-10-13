"""Scorecard contract (SCORING_ENGINE). Eliminatory criteria stay independent of any aggregate."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from evalkit.contracts.base import ContractModel
from evalkit.contracts.enums import Dimension, EvalStatus, MeasurementKind


class ConfidenceInterval(ContractModel):
    low: float
    high: float
    level: float = Field(ge=0, lt=1, description="e.g. 0.95")
    method: str = Field(description="e.g. 'wilson', 'bootstrap_bca', 't'.")
    n: int = Field(ge=0)


class DimensionScore(ContractModel):
    dimension: Dimension
    status: EvalStatus
    measurement: MeasurementKind
    pass_rate: float | None = Field(default=None, ge=0, le=1)
    mean_score: float | None = Field(default=None, ge=0, le=1)
    ci: ConfidenceInterval | None = None
    n_runs: int = Field(ge=0)
    n_evaluated: int = Field(ge=0)
    critical_failures: int = Field(default=0, ge=0)
    note: str | None = None


class Scorecard(ContractModel):
    scorecard_id: str
    project_id: str
    agent_id: str
    agent_version: str
    campaign_id: str
    generated_at: datetime
    evalkit_version: str
    overall_status: EvalStatus
    eliminatory_failures: list[str] = Field(
        default_factory=list, description="Scenario/evaluator ids with blocking FAIL."
    )
    dimensions: list[DimensionScore]
    aggregate_score: float | None = Field(default=None, ge=0, le=1)
    aggregate_formula: str | None = Field(
        default=None,
        description="Formula, weights, exclusions (human-readable); required with aggregate_score.",
    )
    missing_dimensions: list[Dimension] = Field(default_factory=list)
    total_cost: float | None = None
    currency: str = "USD"
    cost_status: str | None = None
    mean_latency_ms: float | None = None
    baseline_campaign_id: str | None = None
    regressions: list[str] = Field(default_factory=list)
    validity_warnings: list[str] = Field(
        default_factory=list, description="Coverage, overfitting, drift, non-equivalence warnings."
    )
