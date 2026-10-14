"""Policy port. Agents cannot raise their own level nor change success criteria."""

from __future__ import annotations

from typing import Protocol

from pydantic import Field

from evalkit.contracts import AutonomyLevel, ContractModel


class Action(ContractModel):
    kind: str
    target: str
    actor: str
    required_level: AutonomyLevel = Field(
        default=AutonomyLevel.AUTOMATIC,
        description="Level the caller declares; the policy engine never goes below the kind's level.",
    )
    details: dict[str, object] = Field(default_factory=dict)


class PolicyDecision(ContractModel):
    allowed: bool
    reason: str
    requires_human: bool = False


class PolicyEngine(Protocol):
    def decide(self, action: Action) -> PolicyDecision: ...
