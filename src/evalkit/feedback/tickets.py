"""Ticket runtime: incident detection from stored scorecards/results, structured tickets with
evidence references, fingerprint-based reconciliation (never merging, never erasing),
versioned state workflow with an append-only history.
"""

from __future__ import annotations

import contextlib
import hashlib
from collections import Counter

from evalkit.audit import make_event
from evalkit.contracts import (
    Criticality,
    EvalStatus,
    EventType,
    Scorecard,
    Severity,
    Ticket,
    TicketStatus,
    new_id,
    utcnow,
)
from evalkit.contracts.ticket import Hypothesis
from evalkit.storage.sqlite import SQLiteRepository

WORKFLOW_VERSION = "1.0.0"
TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {
        TicketStatus.TRIAGED,
        TicketStatus.DUPLICATE,
        TicketStatus.REJECTED,
        TicketStatus.CLOSED,
    },
    TicketStatus.TRIAGED: {TicketStatus.DIAGNOSED, TicketStatus.REJECTED, TicketStatus.CLOSED},
    TicketStatus.DIAGNOSED: {TicketStatus.FIX_PROPOSED, TicketStatus.REJECTED, TicketStatus.CLOSED},
    TicketStatus.FIX_PROPOSED: {
        TicketStatus.TESTING,
        TicketStatus.DIAGNOSED,
        TicketStatus.REJECTED,
    },
    TicketStatus.TESTING: {TicketStatus.VALIDATED, TicketStatus.DIAGNOSED, TicketStatus.REJECTED},
    TicketStatus.VALIDATED: {TicketStatus.CLOSED},
    TicketStatus.REJECTED: {TicketStatus.DIAGNOSED},
    TicketStatus.DUPLICATE: set(),
    TicketStatus.CLOSED: set(),
}
"""Versioned workflow. VALIDATED is only reachable from TESTING; nothing reopens CLOSED."""

ERROR_RATE_THRESHOLD = 0.2


def fingerprint(project_id: str, agent_id: str, kind: str, key: str) -> str:
    return hashlib.sha256(f"{project_id}|{agent_id}|{kind}|{key}".encode()).hexdigest()[:16]


class TicketStore:
    def __init__(self, repo: SQLiteRepository, *, actor: str = "system") -> None:
        self.repo = repo
        self.actor = actor

    # --------------------------------------------------------------- creation
    def open(
        self,
        *,
        project_id: str,
        agent_id: str,
        agent_version: str,
        kind: str,
        key: str,
        title: str,
        description: str,
        expected: str,
        observed: str,
        severity: Criticality,
        impact: str,
        evidence_refs: list[str],
        component: str | None = None,
        campaign_id: str | None = None,
    ) -> Ticket:
        """Open a ticket, or link it as DUPLICATE of an open one with the same fingerprint.
        Both tickets are kept; the original's history records the new occurrence."""
        fp = fingerprint(project_id, agent_id, kind, key)
        now = utcnow()
        existing = [
            t
            for t in self.repo.find_tickets_by_fingerprint(project_id, fp)
            if t.status not in (TicketStatus.CLOSED, TicketStatus.REJECTED, TicketStatus.DUPLICATE)
        ]
        ticket = Ticket(
            ticket_id=new_id("tck"),
            created_at=now,
            updated_at=now,
            project_id=project_id,
            agent_id=agent_id,
            agent_version=agent_version,
            component=component,
            title=title,
            description=description,
            expected=expected,
            observed=observed,
            severity=severity,
            impact=impact,
            evidence_refs=evidence_refs,
            priority=_priority(severity),
            status=TicketStatus.OPEN,
            workflow_version=WORKFLOW_VERSION,
            history=[f"{now.isoformat()} OPEN by {self.actor} (campaign {campaign_id})"],
        )
        with self.repo.transaction():
            if existing:
                original = existing[0]
                ticket = ticket.model_copy(
                    update={
                        "status": TicketStatus.DUPLICATE,
                        "related_tickets": [original.ticket_id],
                        "history": [
                            *ticket.history,
                            f"{now.isoformat()} DUPLICATE of {original.ticket_id}",
                        ],
                    }
                )
                original = original.model_copy(
                    update={
                        "updated_at": now,
                        "related_tickets": [*original.related_tickets, ticket.ticket_id],
                        "evidence_refs": list(
                            dict.fromkeys([*original.evidence_refs, *evidence_refs])
                        ),
                        "history": [
                            *original.history,
                            f"{now.isoformat()} new occurrence {ticket.ticket_id} (version {agent_version}, campaign {campaign_id})",
                        ],
                    }
                )
                self.repo.save_ticket(original, fp)
            self.repo.save_ticket(ticket, fp)
        self.repo.emit(
            make_event(
                EventType.INCIDENT_OPENED,
                component="feedback",
                actor=self.actor,
                severity=Severity.WARNING
                if severity in (Criticality.HIGH, Criticality.CRITICAL)
                else Severity.INFO,
                project_id=project_id,
                agent_id=agent_id,
                agent_version=agent_version,
                campaign_id=campaign_id,
                payload={
                    "ticket_id": ticket.ticket_id,
                    "kind": kind,
                    "fingerprint": fp,
                    "duplicate_of": ticket.related_tickets[0]
                    if ticket.status is TicketStatus.DUPLICATE
                    else None,
                    "severity": severity.value,
                },
            )
        )
        return ticket

    # -------------------------------------------------------------- workflow
    def transition(
        self,
        ticket_id: str,
        new_status: TicketStatus,
        note: str,
        *,
        decision: str | None = None,
        proposed_fix: str | None = None,
        hypotheses: list[Hypothesis] | None = None,
        related_tests: list[str] | None = None,
        post_fix_results: list[str] | None = None,
        component: str | None = None,
    ) -> Ticket:
        ticket = self.repo.get_ticket(ticket_id)
        if new_status not in TRANSITIONS[ticket.status]:
            msg = f"transition {ticket.status.value} -> {new_status.value} not allowed by workflow {WORKFLOW_VERSION}"
            raise ValueError(msg)
        now = utcnow()
        update: dict[str, object] = {
            "status": new_status,
            "updated_at": now,
            "history": [
                *ticket.history,
                f"{now.isoformat()} {ticket.status.value} -> {new_status.value} by {self.actor}: {note}",
            ],
        }
        if decision is not None:
            update["decision"] = decision
        if proposed_fix is not None:
            update["proposed_fix"] = proposed_fix
        if hypotheses is not None:
            update["hypotheses"] = [*ticket.hypotheses, *hypotheses]
        if related_tests is not None:
            update["related_tests"] = [*ticket.related_tests, *related_tests]
        if post_fix_results is not None:
            update["post_fix_results"] = [*ticket.post_fix_results, *post_fix_results]
        if component is not None:
            update["component"] = component
        ticket = ticket.model_copy(update=update)
        row = self.repo._conn.execute(
            "SELECT fingerprint FROM tickets WHERE ticket_id=?", (ticket_id,)
        ).fetchone()
        with self.repo.transaction():
            self.repo.save_ticket(ticket, row["fingerprint"] if row else None)
        if new_status in (TicketStatus.VALIDATED, TicketStatus.REJECTED, TicketStatus.CLOSED):
            self.repo.emit(
                make_event(
                    EventType.VALIDATION_DECISION,
                    component="feedback",
                    actor=self.actor,
                    project_id=ticket.project_id,
                    agent_id=ticket.agent_id,
                    agent_version=ticket.agent_version,
                    payload={
                        "ticket_id": ticket_id,
                        "status": new_status.value,
                        "note": note,
                        "decision": decision,
                    },
                )
            )
        return ticket

    # ------------------------------------------------------------- detection
    def detect_incidents(self, scorecard: Scorecard) -> list[Ticket]:
        """Open tickets from a scorecard: eliminatory failures (grouped by scenario+evaluator),
        regressions, and a run error rate above the threshold. Idempotent through fingerprints."""
        tickets: list[Ticket] = []
        runs = list(self.repo.list_runs(scorecard.campaign_id))
        results = {r.run_id: list(self.repo.list_results(r.run_id)) for r in runs}
        crit: dict[str, Criticality] = {}
        for r in runs:
            with contextlib.suppress(KeyError):
                crit[r.scenario_id] = self.repo.get_scenario(
                    r.scenario_id, r.scenario_version
                ).criticality

        groups: Counter[tuple[str, str]] = Counter()
        evidence: dict[tuple[str, str], list[str]] = {}
        observed: dict[tuple[str, str], str] = {}
        for r in runs:
            for res in results[r.run_id]:
                if res.blocking and res.status is EvalStatus.FAIL:
                    key = (r.scenario_id, res.evaluator_id)
                    groups[key] += 1
                    evidence.setdefault(key, []).extend([res.result_id, r.run_id])
                    observed.setdefault(
                        key, res.evidence[0].summary if res.evidence else res.message
                    )
        for (scenario_id, evaluator_id), count in groups.items():
            severity = crit.get(scenario_id, Criticality.MEDIUM)
            tickets.append(
                self.open(
                    project_id=scorecard.project_id,
                    agent_id=scorecard.agent_id,
                    agent_version=scorecard.agent_version,
                    kind="eliminatory_failure",
                    key=f"{scenario_id}:{evaluator_id}",
                    title=f"Eliminatory failure on {scenario_id} ({evaluator_id})",
                    description=f"{count} blocking FAIL result(s) in campaign {scorecard.campaign_id}",
                    expected=f"{evaluator_id} PASS on {scenario_id}",
                    observed=observed[(scenario_id, evaluator_id)][:500],
                    severity=severity,
                    impact=f"scenario criticality {severity.value}; overall status {scorecard.overall_status.value}",
                    evidence_refs=[
                        *sorted(set(evidence[(scenario_id, evaluator_id)])),
                        scorecard.scorecard_id,
                    ],
                    component=evaluator_id,
                    campaign_id=scorecard.campaign_id,
                )
            )
        for reg in scorecard.regressions:
            tickets.append(
                self.open(
                    project_id=scorecard.project_id,
                    agent_id=scorecard.agent_id,
                    agent_version=scorecard.agent_version,
                    kind="regression",
                    key=reg.split(":")[0],
                    title=f"Regression vs baseline {scorecard.baseline_campaign_id}: {reg.split(':')[0]}",
                    description=reg,
                    expected="no degradation of the valid-run rate versus the baseline",
                    observed=reg,
                    severity=Criticality.HIGH,
                    impact="paired comparison shows a degradation",
                    evidence_refs=[
                        scorecard.scorecard_id,
                        scorecard.campaign_id,
                        scorecard.baseline_campaign_id or "",
                    ],
                    component="comparison",
                    campaign_id=scorecard.campaign_id,
                )
            )
        errors = sum(1 for r in runs if r.error)
        if runs and errors / len(runs) >= ERROR_RATE_THRESHOLD:
            tickets.append(
                self.open(
                    project_id=scorecard.project_id,
                    agent_id=scorecard.agent_id,
                    agent_version=scorecard.agent_version,
                    kind="error_rate",
                    key="runs",
                    title=f"Run error rate {errors}/{len(runs)}",
                    description=f"{errors} of {len(runs)} runs ended with an agent error",
                    expected=f"error rate below {ERROR_RATE_THRESHOLD:.0%}",
                    observed=f"{errors / len(runs):.0%}",
                    severity=Criticality.HIGH,
                    impact="reliability",
                    evidence_refs=[
                        *[r.run_id for r in runs if r.error][:20],
                        scorecard.scorecard_id,
                    ],
                    component="adapter",
                    campaign_id=scorecard.campaign_id,
                )
            )
        return tickets


def _priority(severity: Criticality) -> int:
    return {
        Criticality.CRITICAL: 1,
        Criticality.HIGH: 2,
        Criticality.MEDIUM: 3,
        Criticality.LOW: 4,
    }[severity]


def render_backlog_markdown(repo: SQLiteRepository, project_id: str) -> str:
    tickets = list(repo.list_tickets(project_id))
    lines = [
        f"# Backlog — project {project_id}",
        "",
        f"Generated from the ticket store ({len(tickets)} tickets, workflow {WORKFLOW_VERSION}). "
        "Duplicates stay listed and linked; nothing is erased.",
        "",
        "| id | status | prio | severity | agent | title | related | updated |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for t in sorted(tickets, key=lambda x: (x.priority, x.created_at)):
        lines.append(
            f"| {t.ticket_id} | {t.status.value} | {t.priority} | {t.severity.value} | {t.agent_id} v{t.agent_version} "
            f"| {t.title} | {', '.join(t.related_tickets) or ''} | {t.updated_at:%Y-%m-%d} |"
        )
    for t in sorted(tickets, key=lambda x: (x.priority, x.created_at)):
        lines += [
            "",
            f"## {t.ticket_id} — {t.title}",
            "",
            f"- Status {t.status.value} · priority {t.priority} · severity {t.severity.value} · component {t.component or 'n/a'}",
            f"- Expected: {t.expected}",
            f"- Observed: {t.observed}",
            f"- Impact: {t.impact}",
            f"- Evidence: {', '.join(t.evidence_refs[:12])}{' …' if len(t.evidence_refs) > 12 else ''}",
        ]
        if t.hypotheses:
            lines += ["- Hypotheses:"] + [f"  - [{h.status}] {h.text}" for h in t.hypotheses]
        if t.proposed_fix:
            lines.append(f"- Proposed fix: {t.proposed_fix}")
        if t.post_fix_results:
            lines.append(f"- Post-fix results: {', '.join(t.post_fix_results)}")
        if t.decision:
            lines.append(f"- Decision: {t.decision}")
        lines += ["- History:"] + [f"  - {h}" for h in t.history]
    return "\n".join(lines) + "\n"
