"""Canonical, versioned, model-agnostic test scenario. See docs/EVALUATION_PROTOCOL.md."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from evalkit.contracts.base import ContractModel
from evalkit.contracts.enums import Criticality, DatasetKind, Dimension

_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]{2,127}$"


class VerificationSpec(ContractModel):
    """One verification method applied to the run. Resolved by the evaluator registry."""

    evaluator: str = Field(
        description="Registered evaluator id, e.g. 'exact_match', 'json_schema'."
    )
    dimension: Dimension
    params: dict[str, object] = Field(default_factory=dict)
    blocking: bool = Field(
        default=False, description="If True, a FAIL is eliminatory regardless of other scores."
    )
    weight: float | None = Field(default=None, ge=0, description="Optional scoring weight.")


class BudgetLimit(ContractModel):
    max_tokens: int | None = Field(default=None, ge=0)
    max_cost: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    max_latency_ms: float | None = Field(default=None, ge=0)


class SuccessCriteria(ContractModel):
    min_pass_rate: float | None = Field(default=None, ge=0, le=1)
    required_dimensions: list[Dimension] = Field(default_factory=list)
    description: str | None = None


class Provenance(ContractModel):
    author: str
    created_at: datetime
    origin: str = Field(
        description="Where the scenario comes from (handwritten, incident replay, ...)."
    )
    revision: str | None = Field(default=None, description="VCS revision or document version.")


class Scenario(ContractModel):
    scenario_id: str = Field(pattern=_ID_PATTERN)
    version: str = Field(description="Scenario version (semver). Changing expectations bumps it.")
    project_id: str = Field(pattern=_ID_PATTERN)
    agent_id: str = Field(pattern=_ID_PATTERN)
    name: str
    description: str
    objective: str
    inputs: dict[str, object] = Field(description="Inputs handed to the adapter.")
    context: dict[str, object] = Field(default_factory=dict, description="Context and fixtures.")
    expected_behavior: str
    constraints: list[str] = Field(default_factory=list, description="Mandatory constraints.")
    reference_outputs: dict[str, object] = Field(
        default_factory=dict, description="Ground-truth references used by evaluators."
    )
    sources_of_truth: list[str] = Field(default_factory=list)
    verifications: list[VerificationSpec] = Field(min_length=1)
    criticality: Criticality = Criticality.MEDIUM
    repetitions: int = Field(default=1, ge=1)
    budget: BudgetLimit = Field(default_factory=BudgetLimit)
    success: SuccessCriteria = Field(default_factory=SuccessCriteria)
    dataset: DatasetKind = DatasetKind.DEVELOPMENT
    tags: list[str] = Field(default_factory=list)
    provenance: Provenance

    @field_validator("version")
    @classmethod
    def _semver(cls, v: str) -> str:
        parts = v.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            msg = "version must be MAJOR.MINOR.PATCH"
            raise ValueError(msg)
        return v
