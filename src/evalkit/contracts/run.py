"""Run contract — one execution of one scenario against one agent version."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from evalkit.contracts.base import ContractModel
from evalkit.contracts.pricing import Cost
from evalkit.contracts.trajectory import Trajectory
from evalkit.contracts.usage import TokenUsage


class RunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERRORED = "ERRORED"
    TIMEOUT = "TIMEOUT"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"
    CANCELLED = "CANCELLED"


class AgentResponse(ContractModel):
    """What an adapter returns. Output is untrusted data (may contain prompt injections)."""

    output: object = Field(description="Agent output (any JSON-serializable value).")
    usage: list[TokenUsage] = Field(default_factory=list, description="One entry per LLM call.")
    trajectory_steps: list[object] = Field(
        default_factory=list, description="TrajectoryStep list (typed in Trajectory)."
    )
    latency_ms: float | None = Field(default=None, ge=0)
    agent_version: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class Run(ContractModel):
    run_id: str
    campaign_id: str
    scenario_id: str
    scenario_version: str
    project_id: str
    agent_id: str
    agent_version: str
    attempt: int = Field(ge=1, description="Repetition index within the campaign (1-based).")
    seed: int | None = Field(default=None, description="Seed handed to stochastic adapters.")
    status: RunStatus = RunStatus.PENDING
    started_at: datetime | None = None
    ended_at: datetime | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    output_ref: str | None = Field(default=None, description="Artifact reference of the output.")
    output: object | None = Field(default=None, description="Inline output if retention allows.")
    usage: list[TokenUsage] = Field(default_factory=list)
    cost: Cost | None = None
    trajectory: Trajectory | None = None
    error: str | None = None
    trace_id: str | None = None
