"""Audit event contract (AUDIT_TRAIL). Append-only at the logical level.

Corrections are new events (``event_type=correction``, ``corrects=<event_id>``), never edits.
Absent data is ``None`` — explicitly unknown, never defaulted.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from evalkit.contracts.base import ContractModel
from evalkit.contracts.enums import Severity
from evalkit.contracts.pricing import Cost
from evalkit.contracts.usage import TokenUsage


class EventType(StrEnum):
    PROJECT_CREATED = "project.created"
    CONFIG_CHANGED = "config.changed"
    CAMPAIGN_STARTED = "campaign.started"
    CAMPAIGN_ENDED = "campaign.ended"
    SCENARIO_STARTED = "scenario.started"
    SCENARIO_ENDED = "scenario.ended"
    AGENT_CALLED = "agent.called"
    MODEL_CALLED = "model.called"
    TOOL_CALLED = "tool.called"
    USAGE_RECORDED = "usage.recorded"
    ERROR = "error"
    RETRY = "retry"
    BUDGET_RESERVED = "budget.reserved"
    BUDGET_SETTLED = "budget.settled"
    BUDGET_RELEASED = "budget.released"
    BUDGET_THRESHOLD = "budget.threshold"
    BUDGET_BLOCKED = "budget.blocked"
    EVALUATION_RESULT = "evaluation.result"
    BASELINE_CHANGED = "baseline.changed"
    REGRESSION_DETECTED = "regression.detected"
    INCIDENT_OPENED = "incident.opened"
    FIX_PROPOSED = "fix.proposed"
    TEST_RESULT = "test.result"
    VALIDATION_DECISION = "validation.decision"
    VERSION_CHANGED = "version.changed"
    MIGRATION = "migration"
    PERMISSION_CHANGED = "permission.changed"
    HUMAN_INTERVENTION = "human.intervention"
    CORRECTION = "correction"


class AuditEvent(ContractModel):
    event_id: str
    timestamp: datetime
    event_type: EventType
    severity: Severity = Severity.INFO
    actor: str = Field(
        description="'system', 'scheduler', 'cli:<user>', 'api:<key_id>', 'agent:<id>'."
    )
    project_id: str | None = None
    agent_id: str | None = None
    agent_version: str | None = None
    campaign_id: str | None = None
    run_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    component: str = Field(description="Emitting module, e.g. 'core', 'cost_controller'.")
    version: str = Field(description="EVALKIT version that emitted the event.")
    status: str | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    usage: TokenUsage | None = None
    cost: Cost | None = None
    payload_ref: str | None = Field(
        default=None, description="Artifact reference, never inline secrets."
    )
    payload: dict[str, object] = Field(
        default_factory=dict, description="Small, redacted, structured payload."
    )
    correlation_id: str | None = None
    corrects: str | None = Field(default=None, description="event_id this event corrects.")
    sequence: int | None = Field(
        default=None, ge=0, description="Monotonic per-store sequence assigned by the store."
    )
