"""Statistical result contracts (internal, but serialized into reports)."""

from __future__ import annotations

from pydantic import Field

from evalkit.contracts import ContractModel, EvalStatus


class IntervalResult(ContractModel):
    estimate: float
    low: float
    high: float
    level: float
    method: str
    n: int
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ComparisonResult(ContractModel):
    """Candidate vs baseline. ``conclusion`` is INCONCLUSIVE when data cannot decide."""

    metric: str
    baseline_estimate: float
    candidate_estimate: float
    difference: float
    ci: IntervalResult | None = None
    p_value: float | None = None
    effect_size: float | None = None
    effect_size_method: str | None = None
    paired: bool
    n_baseline: int
    n_candidate: int
    multiple_comparison_correction: str | None = None
    conclusion: EvalStatus
    rationale: str


class VarianceDecomposition(ContractModel):
    """Separates generation, scenario, environment and evaluator variability."""

    between_generations: float | None = None
    between_scenarios: float | None = None
    between_environments: float | None = None
    between_evaluators: float | None = None
    method: str
    note: str | None = None
