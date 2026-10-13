"""Evaluation result contract. Control state and conclusion are always separate."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from evalkit.contracts.base import ContractModel
from evalkit.contracts.enums import ControlState, Dimension, EvalStatus, MeasurementKind
from evalkit.contracts.pricing import Cost
from evalkit.contracts.usage import TokenUsage


class Evidence(ContractModel):
    kind: str = Field(description="e.g. 'diff', 'schema_error', 'reference', 'judge_rationale'.")
    summary: str
    ref: str | None = Field(default=None, description="Artifact reference for the full evidence.")


class EvaluationResult(ContractModel):
    result_id: str
    run_id: str
    evaluator_id: str
    evaluator_version: str
    dimension: Dimension
    control_state: ControlState
    status: EvalStatus
    measurement: MeasurementKind
    score: float | None = Field(default=None, ge=0, le=1, description="Normalised score if any.")
    value: float | None = Field(default=None, description="Raw measured value (latency ms, ...).")
    unit: str | None = None
    blocking: bool = False
    message: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    evaluator_usage: list[TokenUsage] = Field(
        default_factory=list, description="LLM usage of the evaluator itself (kept separate)."
    )
    evaluator_cost: Cost | None = None
    evaluated_at: datetime

    @model_validator(mode="after")
    def _coherence(self) -> EvaluationResult:
        if self.control_state is not ControlState.COMPLETED and self.status in (
            EvalStatus.PASS,
            EvalStatus.FAIL,
            EvalStatus.WARNING,
        ):
            msg = "a non-completed control cannot conclude PASS/FAIL/WARNING"
            raise ValueError(msg)
        if self.measurement is MeasurementKind.UNAVAILABLE and self.score is not None:
            msg = "UNAVAILABLE measurement cannot carry a score"
            raise ValueError(msg)
        return self
