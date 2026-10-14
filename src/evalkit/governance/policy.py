"""Autonomy policy (docs/AUTONOMY_POLICY.md) enforced in code.

A project declares ``autonomy.max_level`` (1 to 4, default 2) and, for level 3, an explicit
``apply_perimeter`` (list of action kinds allowed to be applied automatically). Actions
that change evaluation rules, permissions, HOLDOUT sets or publish externally are always
level 4 — no configuration can lower them. Actors of kind ``agent:*`` can never obtain a
decision above level 2, whatever the project says.
"""

from __future__ import annotations

from pydantic import Field

from evalkit.contracts import AutonomyLevel, ContractModel
from evalkit.governance.interfaces import Action, PolicyDecision

ALWAYS_HUMAN: frozenset[str] = frozenset(
    {
        "change_success_criteria",
        "change_holdout",
        "change_permissions",
        "change_budget",
        "publish_external",
        "delete_data",
        "apply_fix_production",
    }
)
"""Action kinds that are level 4 regardless of configuration."""

LEVEL_OF_KIND: dict[str, AutonomyLevel] = {
    "run_campaign": AutonomyLevel.AUTOMATIC,
    "open_ticket": AutonomyLevel.AUTOMATIC,
    "build_scorecard": AutonomyLevel.AUTOMATIC,
    "propose_fix": AutonomyLevel.ISOLATED_AUTOMATIC,
    "run_experiment": AutonomyLevel.ISOLATED_AUTOMATIC,
    "record_learning": AutonomyLevel.ISOLATED_AUTOMATIC,
    "apply_fix_low_risk": AutonomyLevel.CONTROLLED_APPLY,
}


class AutonomyConfig(ContractModel):
    max_level: int = Field(default=2, ge=1, le=4)
    apply_perimeter: list[str] = Field(
        default_factory=list,
        description="Action kinds allowed at level 3 (e.g. 'apply_fix_low_risk').",
    )


class ProjectPolicyEngine:
    def __init__(self, config: AutonomyConfig | None = None) -> None:
        self.config = config or AutonomyConfig()

    def required_level(self, kind: str) -> AutonomyLevel:
        if kind in ALWAYS_HUMAN:
            return AutonomyLevel.HUMAN_VALIDATION
        return LEVEL_OF_KIND.get(kind, AutonomyLevel.HUMAN_VALIDATION)

    def decide(self, action: Action) -> PolicyDecision:
        required = max(action.required_level, self.required_level(action.kind))
        if action.actor.startswith("agent:") and required > AutonomyLevel.ISOLATED_AUTOMATIC:
            return PolicyDecision(
                allowed=False,
                reason=f"actor {action.actor!r} cannot obtain level {int(required)}: agents never apply",
                requires_human=True,
            )
        if required is AutonomyLevel.HUMAN_VALIDATION:
            return PolicyDecision(
                allowed=False,
                reason=f"{action.kind}: level 4, human validation required",
                requires_human=True,
            )
        if int(required) > self.config.max_level:
            return PolicyDecision(
                allowed=False,
                reason=f"{action.kind}: level {int(required)} > project max_level {self.config.max_level}",
                requires_human=True,
            )
        if (
            required is AutonomyLevel.CONTROLLED_APPLY
            and action.kind not in self.config.apply_perimeter
        ):
            return PolicyDecision(
                allowed=False,
                reason=f"{action.kind}: level 3 but not in the approved apply_perimeter",
                requires_human=True,
            )
        return PolicyDecision(allowed=True, reason=f"{action.kind}: level {int(required)} allowed")
