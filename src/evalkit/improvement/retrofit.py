"""Retrofit cycle: OBSERVE → CLASSIFY → DIAGNOSE → PRIORITIZE → PROPOSE → ISOLATE → TEST →
COMPARE → DECIDE → RECORD → LEARN. Every step emits an audit event (``payload.step``).

What it is: a verified, provenance-tracked loop around a *configuration* fix (agent params or
version) tested in an isolated copy of the project without its HOLDOUT scenarios, compared
to both the broken campaign and the last known-good campaign, and decided by the project's
autonomy policy. What it is not: training, automatic production changes (level 4 unless the
project explicitly opens a level-3 perimeter), or a guarantee — a fix that passes on the
DEVELOPMENT set only earns a learning in status ``observed`` until ``confirm`` reproduces it
on a DEEP campaign with HOLDOUT included.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from evalkit import __version__
from evalkit.audit import make_event
from evalkit.contracts import (
    AutonomyLevel,
    Campaign,
    DatasetKind,
    EvalStatus,
    EventType,
    Profile,
    Severity,
    Ticket,
    TicketStatus,
    new_id,
    utcnow,
)
from evalkit.contracts.ticket import Hypothesis
from evalkit.core.orchestrator import CampaignRunner
from evalkit.core.project import load_project, load_scenarios
from evalkit.feedback import TicketStore
from evalkit.governance import Action, ProjectPolicyEngine
from evalkit.improvement.learnings import LearningStore
from evalkit.scoring import build_scorecard
from evalkit.stats import paired_comparison
from evalkit.storage.sqlite import SQLiteRepository

FixProvider = Callable[["RetrofitContext"], dict[str, Any] | None]
"""Returns the new agent config (adapter/version/params) or None when it has nothing to propose."""

MAX_ITERATIONS_DEFAULT = 2


@dataclass
class RetrofitContext:
    repo: SQLiteRepository
    project_dir: Path
    agent_id: str
    broken: Campaign
    good: Campaign
    ticket: Ticket
    broken_config: dict[str, Any]
    good_config: dict[str, Any] | None


@dataclass
class RetrofitResult:
    experiment_id: str
    ticket_id: str
    decision: str
    rationale: str
    candidate_campaign_id: str | None = None
    fix: dict[str, Any] | None = None
    learning_id: str | None = None
    steps: list[str] = field(default_factory=list)


def revert_to_last_good(ctx: RetrofitContext) -> dict[str, Any] | None:
    """Built-in fix provider: revert the agent config to the last known-good campaign's."""
    if ctx.good_config is None or ctx.good_config == ctx.broken_config:
        return None
    return dict(ctx.good_config)


def params_override(params: dict[str, Any], version: str | None = None) -> FixProvider:
    """Fix provider from an explicit params patch (CLI ``--params``)."""

    def provide(ctx: RetrofitContext) -> dict[str, Any] | None:
        cfg = dict(ctx.broken_config)
        cfg["params"] = {**dict(cfg.get("params", {})), **params}
        if version:
            cfg["version"] = version
        return cfg

    return provide


def _agent_config_of(repo: SQLiteRepository, campaign_id: str) -> dict[str, Any] | None:
    for e in repo.query(campaign_id=campaign_id, event_type=EventType.CAMPAIGN_STARTED.value):
        cfg = e.payload.get("agent_config")
        if isinstance(cfg, dict):
            return cfg
    return None


class RetrofitCycle:
    def __init__(
        self,
        repo: SQLiteRepository,
        *,
        actor: str = "cli",
        fix_provider: FixProvider | None = None,
        max_iterations: int = MAX_ITERATIONS_DEFAULT,
        seed: int = 0,
    ) -> None:
        self.repo = repo
        self.actor = actor
        self.fix_provider = fix_provider or revert_to_last_good
        self.max_iterations = max(1, max_iterations)
        self.seed = seed
        self.tickets = TicketStore(repo, actor=actor)
        self.learnings = LearningStore(repo, actor=actor)

    def _step(
        self,
        step: str,
        campaign: Campaign,
        experiment_id: str,
        payload: dict[str, Any] | None = None,
        severity: Severity = Severity.INFO,
    ) -> None:
        self.repo.emit(
            make_event(
                EventType.FIX_PROPOSED
                if step == "PROPOSE"
                else EventType.TEST_RESULT
                if step in ("TEST", "COMPARE")
                else EventType.VALIDATION_DECISION
                if step == "DECIDE"
                else EventType.CONFIG_CHANGED,
                component="improvement",
                actor=self.actor,
                severity=severity,
                project_id=campaign.project_id,
                agent_id=campaign.agent_id,
                agent_version=campaign.agent_version,
                campaign_id=campaign.campaign_id,
                payload={"step": step, "experiment_id": experiment_id, **(payload or {})},
            )
        )

    def run(
        self, project_dir: Path, agent_id: str, *, broken_campaign_id: str, good_campaign_id: str
    ) -> RetrofitResult:
        broken = self.repo.get_campaign(broken_campaign_id)
        good = self.repo.get_campaign(good_campaign_id)
        if broken.agent_id != agent_id or good.agent_id != agent_id:
            msg = "both campaigns must belong to the agent under retrofit"
            raise ValueError(msg)
        config = load_project(project_dir)
        policy = ProjectPolicyEngine(config.autonomy)
        experiment_id = new_id("exp")
        steps: list[str] = []

        # OBSERVE — scorecard with baseline, incident tickets
        card = self.repo.scorecard_for_campaign(broken.campaign_id)
        if card is None or card.baseline_campaign_id != good.campaign_id:
            broken = broken.model_copy(update={"baseline_campaign_id": good.campaign_id})
            with self.repo.transaction():
                self.repo.save_campaign(broken)
            card = build_scorecard(self.repo, broken.campaign_id, weights=config.weights or None)
        opened = self.tickets.detect_incidents(card)
        primary = next((t for t in opened if t.status is not TicketStatus.DUPLICATE), None)
        if primary is None:
            # reuse the open original behind a duplicate, or stop: nothing to fix
            dup = next((t for t in opened if t.related_tickets), None)
            primary = self.repo.get_ticket(dup.related_tickets[0]) if dup else None
        self._step(
            "OBSERVE",
            broken,
            experiment_id,
            {"scorecard_id": card.scorecard_id, "tickets": [t.ticket_id for t in opened]},
        )
        steps.append("OBSERVE")
        if primary is None:
            self._record_experiment(
                experiment_id,
                broken,
                None,
                "NOTHING_TO_FIX",
                "scorecard shows no eliminatory failure, regression or error-rate incident",
                None,
                None,
            )
            return RetrofitResult(
                experiment_id, "", "NOTHING_TO_FIX", "no incident detected", steps=steps
            )
        if primary.status in (TicketStatus.VALIDATED, TicketStatus.CLOSED):
            rationale = (
                f"ticket {primary.ticket_id} is already {primary.status.value}: "
                "a decided ticket is never reworked; close it or open a new incident"
            )
            self._record_experiment(
                experiment_id, broken, primary.ticket_id, "ALREADY_DECIDED", rationale, None, None
            )
            return RetrofitResult(
                experiment_id, primary.ticket_id, "ALREADY_DECIDED", rationale, steps=steps
            )

        # CLASSIFY
        kind = (
            "regression"
            if primary.component == "comparison"
            else "eliminatory_failure"
            if primary.component not in ("adapter", "comparison")
            else "error_rate"
        )
        if primary.status is TicketStatus.OPEN:
            primary = self.tickets.transition(
                primary.ticket_id,
                TicketStatus.TRIAGED,
                f"classified as {kind}",
                component=primary.component,
            )
        self._step(
            "CLASSIFY", broken, experiment_id, {"ticket_id": primary.ticket_id, "kind": kind}
        )
        steps.append("CLASSIFY")

        # DIAGNOSE — evidence-based hypotheses (rule-based in V1, never LLM-invented)
        broken_cfg = _agent_config_of(self.repo, broken.campaign_id) or {}
        good_cfg = _agent_config_of(self.repo, good.campaign_id)
        hypotheses: list[Hypothesis] = []
        if good_cfg is not None and good_cfg != broken_cfg:
            changed = sorted(
                k for k in set(good_cfg) | set(broken_cfg) if good_cfg.get(k) != broken_cfg.get(k)
            )
            hypotheses.append(
                Hypothesis(
                    text=f"agent configuration changed between good and broken campaigns: {changed}",
                    evidence_refs=[good.campaign_id, broken.campaign_id],
                )
            )
        if good.agent_version != broken.agent_version:
            hypotheses.append(
                Hypothesis(
                    text=f"agent version changed {good.agent_version} -> {broken.agent_version}",
                    evidence_refs=[good.campaign_id, broken.campaign_id],
                )
            )
        if not hypotheses:
            hypotheses.append(
                Hypothesis(
                    text="no configuration difference recorded: behaviour change is external to EVALKIT's view (model, tools, data)",
                    evidence_refs=[broken.campaign_id],
                )
            )
        if primary.status in (TicketStatus.TRIAGED, TicketStatus.REJECTED):
            primary = self.tickets.transition(
                primary.ticket_id,
                TicketStatus.DIAGNOSED,
                f"{len(hypotheses)} hypothesis(es) recorded (experiment {experiment_id})",
                hypotheses=hypotheses,
            )
        self._step(
            "DIAGNOSE",
            broken,
            experiment_id,
            {"ticket_id": primary.ticket_id, "hypotheses": [h.text for h in hypotheses]},
        )
        steps.append("DIAGNOSE")

        # PRIORITIZE
        self._step(
            "PRIORITIZE",
            broken,
            experiment_id,
            {
                "ticket_id": primary.ticket_id,
                "priority": primary.priority,
                "severity": primary.severity.value,
            },
        )
        steps.append("PRIORITIZE")

        ctx = RetrofitContext(
            self.repo, project_dir, agent_id, broken, good, primary, broken_cfg, good_cfg
        )
        decision, rationale = "REJECTED", "no fix could be proposed"
        candidate_id: str | None = None
        fix: dict[str, Any] | None = None
        learning_id: str | None = None
        for iteration in range(1, self.max_iterations + 1):
            # PROPOSE
            verdict = policy.decide(
                Action(
                    kind="propose_fix",
                    target=agent_id,
                    actor=self.actor,
                    required_level=AutonomyLevel.ISOLATED_AUTOMATIC,
                )
            )
            if not verdict.allowed:
                decision, rationale = "HUMAN_VALIDATION_REQUIRED", verdict.reason
                break
            fix = self.fix_provider(ctx)
            if fix is None:
                rationale = "fix provider returned nothing (configs identical?)"
                break
            if primary.status is TicketStatus.DIAGNOSED:
                primary = self.tickets.transition(
                    primary.ticket_id,
                    TicketStatus.FIX_PROPOSED,
                    f"iteration {iteration}",
                    proposed_fix=json.dumps(fix, sort_keys=True),
                )
            self._step(
                "PROPOSE",
                broken,
                experiment_id,
                {"ticket_id": primary.ticket_id, "iteration": iteration, "fix": fix},
            )
            steps.append("PROPOSE")

            # ISOLATE — copy of the project without HOLDOUT scenarios, fix applied
            exp_dir = Path(tempfile.mkdtemp(prefix=f"evalkit-{experiment_id}-"))
            try:
                removed = _isolate(project_dir, exp_dir, agent_id, fix)
                self._step(
                    "ISOLATE",
                    broken,
                    experiment_id,
                    {"experiment_dir": str(exp_dir), "holdout_removed": removed},
                )
                steps.append("ISOLATE")
                # TEST — candidate campaign on the isolated copy, baseline = good
                runner = CampaignRunner(self.repo, actor=self.actor)
                planned = runner.plan(
                    exp_dir,
                    agent_id,
                    profile=Profile.STANDARD,
                    seed=self.seed + iteration,
                    baseline_campaign_id=good.campaign_id,
                )
                import asyncio

                candidate = asyncio.run(runner.execute(planned))
                candidate_id = candidate.campaign_id
                cand_card = build_scorecard(
                    self.repo, candidate.campaign_id, weights=config.weights or None
                )
                if primary.status is TicketStatus.FIX_PROPOSED:
                    primary = self.tickets.transition(
                        primary.ticket_id,
                        TicketStatus.TESTING,
                        f"candidate campaign {candidate.campaign_id}",
                        related_tests=[candidate.campaign_id],
                    )
                self._step(
                    "TEST",
                    broken,
                    experiment_id,
                    {
                        "candidate_campaign_id": candidate.campaign_id,
                        "status": cand_card.overall_status.value,
                        "eliminatory": cand_card.eliminatory_failures,
                    },
                )
                steps.append("TEST")
            finally:
                shutil.rmtree(exp_dir, ignore_errors=True)

            # COMPARE — vs broken (must improve) and vs good (must not regress)
            vs_broken = _compare(self.repo, broken.campaign_id, candidate.campaign_id, self.seed)
            vs_good = _compare(self.repo, good.campaign_id, candidate.campaign_id, self.seed)
            self._step(
                "COMPARE",
                broken,
                experiment_id,
                {
                    "vs_broken": vs_broken,
                    "vs_good": vs_good,
                    "regressions_vs_good": cand_card.regressions,
                },
            )
            steps.append("COMPARE")

            # DECIDE
            fixed = (
                not cand_card.eliminatory_failures
                and cand_card.overall_status
                in (EvalStatus.PASS, EvalStatus.WARNING, EvalStatus.INCONCLUSIVE)
                and not cand_card.regressions
            )
            improved = vs_broken["conclusion"] in ("PASS",) or (
                vs_broken["difference"] > 0 and not cand_card.eliminatory_failures
            )
            if fixed and improved:
                apply = policy.decide(
                    Action(
                        kind="apply_fix_low_risk",
                        target=agent_id,
                        actor=self.actor,
                        required_level=AutonomyLevel.CONTROLLED_APPLY,
                    )
                )
                decision = "APPLY_ALLOWED" if apply.allowed else "HUMAN_VALIDATION_REQUIRED"
                rationale = f"candidate has no eliminatory failure and no regression vs good; vs broken: {vs_broken['rationale']}; policy: {apply.reason}"
                primary = self.tickets.transition(
                    primary.ticket_id,
                    TicketStatus.VALIDATED,
                    rationale,
                    decision=decision,
                    post_fix_results=[cand_card.scorecard_id],
                )
                self._step(
                    "DECIDE",
                    broken,
                    experiment_id,
                    {"decision": decision, "rationale": rationale, "ticket_id": primary.ticket_id},
                )
                steps.append("DECIDE")
                # LEARN (status observed: HOLDOUT not yet seen)
                learning = self.learnings.record(
                    project_id=broken.project_id,
                    scope=f"agent:{agent_id}",
                    statement=f"fix {json.dumps(fix, sort_keys=True)} restores {agent_id} on the DEVELOPMENT set (ticket {primary.ticket_id})",
                    evidence_refs=[
                        broken.campaign_id,
                        good.campaign_id,
                        candidate.campaign_id,
                        cand_card.scorecard_id,
                        primary.ticket_id,
                    ],
                    status="observed",
                )
                learning_id = learning["learning_id"]
                break
            rationale = f"candidate not accepted at iteration {iteration}: eliminatory={cand_card.eliminatory_failures}, regressions={cand_card.regressions}, vs_broken={vs_broken['conclusion']}"
            primary = self.tickets.transition(
                primary.ticket_id,
                TicketStatus.DIAGNOSED,
                rationale,
                post_fix_results=[cand_card.scorecard_id],
            )
            self._step(
                "DECIDE",
                broken,
                experiment_id,
                {"decision": "REJECTED_ITERATION", "rationale": rationale},
                Severity.WARNING,
            )
            steps.append("DECIDE")
            ctx = RetrofitContext(
                self.repo, project_dir, agent_id, broken, good, primary, broken_cfg, good_cfg
            )
        else:
            decision, rationale = (
                "REJECTED",
                f"no accepted candidate after {self.max_iterations} iteration(s): {rationale}",
            )
        if decision == "REJECTED" and primary.status not in (
            TicketStatus.REJECTED,
            TicketStatus.VALIDATED,
            TicketStatus.CLOSED,
        ):
            primary = self.tickets.transition(
                primary.ticket_id, TicketStatus.REJECTED, rationale, decision=decision
            )
            self._step(
                "DECIDE",
                broken,
                experiment_id,
                {"decision": decision, "rationale": rationale},
                Severity.WARNING,
            )
        # RECORD
        self._record_experiment(
            experiment_id,
            broken,
            primary.ticket_id,
            decision,
            rationale,
            candidate_id,
            fix,
            learning_id,
        )
        steps += ["RECORD", "LEARN"] if learning_id else ["RECORD"]
        return RetrofitResult(
            experiment_id,
            primary.ticket_id,
            decision,
            rationale,
            candidate_id,
            fix,
            learning_id,
            steps,
        )

    def confirm(
        self, project_dir: Path, agent_id: str, *, good_campaign_id: str, learning_id: str
    ) -> dict[str, Any]:
        """Reproduce an observed learning on a DEEP campaign (HOLDOUT included) of the real
        project: verified when no eliminatory failure and no regression vs the good baseline."""
        runner = CampaignRunner(self.repo, actor=self.actor)
        planned = runner.plan(
            project_dir,
            agent_id,
            profile=Profile.DEEP,
            seed=self.seed,
            baseline_campaign_id=good_campaign_id,
        )
        import asyncio

        campaign = asyncio.run(runner.execute(planned))
        card = build_scorecard(self.repo, campaign.campaign_id)
        ok = (
            not card.eliminatory_failures
            and not card.regressions
            and card.overall_status is not EvalStatus.FAIL
        )
        status = "verified" if ok else "rejected"
        self.learnings.set_status(
            learning_id, status, evidence_refs=[campaign.campaign_id, card.scorecard_id]
        )
        return {
            "campaign_id": campaign.campaign_id,
            "scorecard_status": card.overall_status.value,
            "learning_status": status,
            "regressions": card.regressions,
            "eliminatory": card.eliminatory_failures,
        }

    def _record_experiment(
        self,
        experiment_id: str,
        broken: Campaign,
        ticket_id: str | None,
        decision: str,
        rationale: str,
        candidate_id: str | None,
        fix: dict[str, Any] | None,
        learning_id: str | None = None,
    ) -> None:
        with self.repo.transaction():
            self.repo._conn.execute(
                "INSERT INTO experiments(experiment_id, created_at, project_id, agent_id, ticket_id, status, json) VALUES (?,?,?,?,?,?,?)",
                (
                    experiment_id,
                    utcnow().isoformat(),
                    broken.project_id,
                    broken.agent_id,
                    ticket_id,
                    decision,
                    json.dumps(
                        {
                            "broken_campaign_id": broken.campaign_id,
                            "baseline_campaign_id": broken.baseline_campaign_id,
                            "candidate_campaign_id": candidate_id,
                            "fix": fix,
                            "rationale": rationale,
                            "learning_id": learning_id,
                            "evalkit_version": __version__,
                        },
                        sort_keys=True,
                    ),
                ),
            )
        self._step(
            "RECORD",
            broken,
            experiment_id,
            {
                "decision": decision,
                "candidate_campaign_id": candidate_id,
                "learning_id": learning_id,
            },
        )


def _isolate(project_dir: Path, exp_dir: Path, agent_id: str, fix: dict[str, Any]) -> int:
    """Copy the project into exp_dir, drop HOLDOUT scenarios, apply the fix to the agent config."""
    shutil.copytree(project_dir, exp_dir, dirs_exist_ok=True)
    config = load_project(exp_dir)
    removed = 0
    root = exp_dir / config.scenarios_dir
    for path in sorted(p for p in root.rglob("*") if p.suffix in {".yaml", ".yml", ".json"}):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if raw.get("dataset") == DatasetKind.HOLDOUT.value:
            path.unlink()
            removed += 1
    data = yaml.safe_load((exp_dir / "evalkit.yaml").read_text(encoding="utf-8")) or {}
    data["agents"][agent_id] = fix
    (exp_dir / "evalkit.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    load_scenarios(exp_dir, load_project(exp_dir))  # fail loudly if the copy is invalid
    return removed


def _scenario_rates(repo: SQLiteRepository, campaign_id: str) -> dict[str, float]:
    from evalkit.scoring.engine import _scenario_valid_rates

    return _scenario_valid_rates(repo, campaign_id)


def _compare(
    repo: SQLiteRepository, baseline_id: str, candidate_id: str, seed: int
) -> dict[str, Any]:
    base, cand = _scenario_rates(repo, baseline_id), _scenario_rates(repo, candidate_id)
    common = sorted(set(base) & set(cand))
    if not common:
        return {
            "conclusion": "INCONCLUSIVE",
            "difference": 0.0,
            "rationale": "no common scenario",
            "n": 0,
        }
    res = paired_comparison(
        "valid_run_rate", [base[k] for k in common], [cand[k] for k in common], seed=seed
    )
    return {
        "conclusion": res.conclusion.value,
        "difference": res.difference,
        "rationale": res.rationale,
        "n": len(common),
    }
