"""Backlog ticket contract (FEEDBACK / IMPROVEMENT). Workflow is versioned; history is kept."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from evalkit.contracts.base import ContractModel
from evalkit.contracts.enums import Criticality


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    TRIAGED = "TRIAGED"
    DIAGNOSED = "DIAGNOSED"
    FIX_PROPOSED = "FIX_PROPOSED"
    TESTING = "TESTING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"
    DUPLICATE = "DUPLICATE"


class Hypothesis(ContractModel):
    text: str
    status: str = Field(default="open", description="'open' | 'confirmed' | 'rejected'.")
    evidence_refs: list[str] = Field(default_factory=list)


class Ticket(ContractModel):
    ticket_id: str
    created_at: datetime
    updated_at: datetime
    project_id: str
    agent_id: str
    agent_version: str
    component: str | None = None
    title: str
    description: str
    expected: str
    observed: str
    severity: Criticality
    impact: str
    evidence_refs: list[str] = Field(default_factory=list, description="run/result/event ids.")
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5, description="1 = highest.")
    status: TicketStatus = TicketStatus.OPEN
    workflow_version: str = "1.0.0"
    proposed_fix: str | None = None
    related_tests: list[str] = Field(default_factory=list)
    post_fix_results: list[str] = Field(default_factory=list)
    decision: str | None = None
    related_tickets: list[str] = Field(
        default_factory=list, description="Similar tickets, kept distinct."
    )
    history: list[str] = Field(default_factory=list, description="Append-only transition log.")
