"""Trajectory contract — V1 collection format enabling V2 Markov analysis.

States, transitions, actions, tools, errors and retries must be identifiable. The format does
NOT assume the agent is Markovian; it records enough to test that hypothesis later.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from evalkit.contracts.base import ContractModel
from evalkit.contracts.usage import TokenUsage


class StepKind(StrEnum):
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    DECISION = "decision"
    RETRY = "retry"
    ERROR = "error"
    HUMAN = "human"
    TERMINAL = "terminal"


class TrajectoryStep(ContractModel):
    index: int = Field(ge=0)
    kind: StepKind
    state: str = Field(description="Observable state label before the action (adapter-defined).")
    next_state: str | None = Field(default=None, description="Observable state after the action.")
    action: str = Field(description="Action label (tool name, decision label, 'generate', ...).")
    tool_name: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    usage: TokenUsage | None = None
    error: str | None = None
    retry_of: int | None = Field(default=None, description="Index of the step being retried.")
    payload_ref: str | None = Field(
        default=None, description="Reference to the stored artifact (inputs/outputs), if retained."
    )
    attributes: dict[str, object] = Field(default_factory=dict)


class Trajectory(ContractModel):
    run_id: str
    steps: list[TrajectoryStep] = Field(default_factory=list)
    terminal_state: str | None = None
    completed: bool = False
