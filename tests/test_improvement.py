"""Phase 6 — governance policy, ticket runtime, retrofit cycle, learnings, self-evaluation.

Acceptance scenarios 18 (incident detection), 19 (ticket creation with dedup), 20 (retrofit
cycle on a simulated regression), 21 (self-evaluation of EVALKIT) — all on simulated agents.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from evalkit.cli.main import app
from evalkit.contracts import (
    AutonomyLevel,
    Criticality,
    EvalStatus,
    EventType,
    Profile,
    TicketStatus,
)
from evalkit.core import CampaignRunner
from evalkit.feedback import TRANSITIONS, TicketStore, fingerprint, render_backlog_markdown
from evalkit.governance import Action, AutonomyConfig, ProjectPolicyEngine
from evalkit.improvement import LearningStore, RetrofitCycle, params_override, self_evaluate
from evalkit.scoring import build_scorecard
from evalkit.storage import SQLiteRepository

runner_cli = CliRunner()

BROKEN_GREETER = {
    "adapter": "sim.deterministic",
    "version": "1.1.0-broken",
    "params": {"behavior": "wrong"},
}


def _run(repo: SQLiteRepository, project: Path, agent: str, **kw: object):  # type: ignore[no-untyped-def]
    runner = CampaignRunner(repo)
    planned = runner.plan(project, agent, profile=Profile.STANDARD, seed=1, **kw)  # type: ignore[arg-type]
    return asyncio.run(runner.execute(planned))


def _set_agent(project: Path, agent: str, config: dict[str, object]) -> None:
    path = project / "evalkit.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["agents"][agent] = config
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path, demo_dir: Path) -> Path:
    dst = tmp_path / "proj"
    shutil.copytree(demo_dir, dst)
    return dst


@pytest.fixture
def regression(repo: SQLiteRepository, project: Path) -> tuple[str, str]:
    """A good campaign of ``greeter`` 1.0.0, then the same agent broken (1.1.0-broken)."""
    good = _run(repo, project, "greeter")
    _set_agent(project, "greeter", BROKEN_GREETER)
    broken = _run(repo, project, "greeter", baseline_campaign_id=good.campaign_id)
    return good.campaign_id, broken.campaign_id


# --- governance ----------------------------------------------------------------------------


def test_policy_levels_and_always_human() -> None:
    engine = ProjectPolicyEngine(AutonomyConfig(max_level=2))
    assert engine.decide(Action(kind="run_campaign", target="a", actor="cli")).allowed
    assert engine.decide(Action(kind="propose_fix", target="a", actor="cli")).allowed
    d = engine.decide(Action(kind="apply_fix_low_risk", target="a", actor="cli"))
    assert not d.allowed and d.requires_human and "max_level" in d.reason
    for kind in ("change_success_criteria", "change_holdout", "change_budget", "publish_external"):
        d = engine.decide(Action(kind=kind, target="a", actor="human"))
        assert not d.allowed and d.requires_human
    # level 4 cannot be lowered by configuration
    lax = ProjectPolicyEngine(AutonomyConfig(max_level=4, apply_perimeter=["apply_fix_low_risk"]))
    assert not lax.decide(Action(kind="change_holdout", target="a", actor="human")).allowed
    assert lax.decide(Action(kind="apply_fix_low_risk", target="a", actor="cli")).allowed
    # level 3 needs an explicit perimeter even when max_level allows it
    no_perimeter = ProjectPolicyEngine(AutonomyConfig(max_level=3))
    assert not no_perimeter.decide(
        Action(kind="apply_fix_low_risk", target="a", actor="cli")
    ).allowed


def test_agent_actors_never_apply() -> None:
    lax = ProjectPolicyEngine(AutonomyConfig(max_level=4, apply_perimeter=["apply_fix_low_risk"]))
    d = lax.decide(Action(kind="apply_fix_low_risk", target="a", actor="agent:greeter"))
    assert not d.allowed and "never apply" in d.reason
    assert lax.decide(Action(kind="propose_fix", target="a", actor="agent:greeter")).allowed
    # an action cannot lower its own required level below the kind's level
    d = lax.decide(
        Action(
            kind="apply_fix_low_risk",
            target="a",
            actor="agent:x",
            required_level=AutonomyLevel.AUTOMATIC,
        )
    )
    assert not d.allowed


# --- tickets (scenarios 18, 19) ------------------------------------------------------------


def test_incident_detection_opens_structured_tickets(
    repo: SQLiteRepository, regression: tuple[str, str]
) -> None:
    _good, broken = regression
    card = build_scorecard(repo, broken)
    assert card.overall_status is EvalStatus.FAIL and card.eliminatory_failures
    store = TicketStore(repo, actor="test")
    opened = store.detect_incidents(card)
    assert opened, "incidents must produce tickets"
    elim = [t for t in opened if t.component == "exact_match"]
    assert elim and elim[0].severity is Criticality.HIGH
    t = elim[0]
    assert t.expected and t.observed and t.impact and t.evidence_refs
    assert card.scorecard_id in t.evidence_refs
    assert t.priority <= 2 and t.status is TicketStatus.OPEN
    assert any(x.component == "comparison" for x in opened), "regression vs baseline ticketed"
    kinds = {e.event_type for e in repo.query(campaign_id=broken)}
    assert EventType.INCIDENT_OPENED in kinds


def test_ticket_dedup_keeps_history_and_links(
    repo: SQLiteRepository, regression: tuple[str, str]
) -> None:
    _good, broken = regression
    card = build_scorecard(repo, broken)
    store = TicketStore(repo, actor="test")
    first = store.detect_incidents(card)
    second = store.detect_incidents(card)
    assert len(second) == len(first)
    assert all(t.status is TicketStatus.DUPLICATE for t in second)
    dup = second[0]
    original = repo.get_ticket(dup.related_tickets[0])
    assert original.status is not TicketStatus.DUPLICATE
    assert dup.ticket_id in original.related_tickets, "both directions linked, nothing erased"
    fp = fingerprint("demo", "greeter", "eliminatory_failure", "demo.greet.001:exact_match")
    assert len(repo.find_tickets_by_fingerprint("demo", fp)) >= 2


def test_ticket_workflow_refuses_invalid_transitions(
    repo: SQLiteRepository, regression: tuple[str, str]
) -> None:
    _good, broken = regression
    store = TicketStore(repo, actor="test")
    t = store.detect_incidents(build_scorecard(repo, broken))[0]
    assert TicketStatus.TRIAGED in TRANSITIONS[TicketStatus.OPEN]
    with pytest.raises(ValueError, match="not allowed"):
        store.transition(t.ticket_id, TicketStatus.VALIDATED, "skip")
    t = store.transition(t.ticket_id, TicketStatus.TRIAGED, "triage")
    t = store.transition(t.ticket_id, TicketStatus.CLOSED, "won't fix", decision="WONTFIX")
    assert t.status is TicketStatus.CLOSED and t.decision == "WONTFIX"
    assert len(t.history) >= 3
    kinds = [e.event_type for e in repo.query(project_id="demo")]
    assert EventType.VALIDATION_DECISION in kinds
    md = render_backlog_markdown(repo, "demo")
    assert t.ticket_id in md and "CLOSED" in md


# --- retrofit cycle (scenario 20) ----------------------------------------------------------


def test_retrofit_cycle_reverts_simulated_regression(
    repo: SQLiteRepository, project: Path, regression: tuple[str, str]
) -> None:
    good, broken = regression
    cycle = RetrofitCycle(repo, actor="test", seed=7)
    res = cycle.run(project, "greeter", broken_campaign_id=broken, good_campaign_id=good)
    assert res.steps == [
        "OBSERVE",
        "CLASSIFY",
        "DIAGNOSE",
        "PRIORITIZE",
        "PROPOSE",
        "ISOLATE",
        "TEST",
        "COMPARE",
        "DECIDE",
        "RECORD",
        "LEARN",
    ]
    # default policy (max_level 2): the fix is validated but never applied automatically
    assert res.decision == "HUMAN_VALIDATION_REQUIRED"
    assert res.fix is not None and res.fix["version"] == "1.0.0"
    assert res.fix["params"]["behavior"] == "reference"
    ticket = repo.get_ticket(res.ticket_id)
    assert ticket.status is TicketStatus.VALIDATED
    assert ticket.hypotheses and ticket.proposed_fix and ticket.related_tests
    assert ticket.post_fix_results
    # the candidate ran on an isolated copy: HOLDOUT scenario never executed there
    cand_runs = list(repo.list_runs(res.candidate_campaign_id or ""))
    assert cand_runs and all(r.scenario_id != "demo.greet.h01" for r in cand_runs)
    cand_card = repo.scorecard_for_campaign(res.candidate_campaign_id or "")
    assert cand_card is not None and cand_card.overall_status is not EvalStatus.FAIL
    # the real project was not modified by the cycle
    cfg = yaml.safe_load((project / "evalkit.yaml").read_text(encoding="utf-8"))
    assert cfg["agents"]["greeter"]["params"]["behavior"] == "wrong"
    # learning recorded as observed with provenance
    learnings = LearningStore(repo).list("demo")
    assert len(learnings) == 1 and learnings[0]["status"] == "observed"
    assert {good, broken, res.candidate_campaign_id} <= set(learnings[0]["evidence_refs"])
    steps = [
        e.payload.get("step")
        for e in repo.query(campaign_id=broken)
        if e.payload.get("experiment_id") == res.experiment_id
    ]
    assert steps.count("ISOLATE") == 1 and "LEARN" not in steps  # LEARN is the learning event
    ok, _ = repo.verify_chain()
    assert ok


def test_retrofit_apply_allowed_only_within_perimeter(
    repo: SQLiteRepository, project: Path, regression: tuple[str, str]
) -> None:
    good, broken = regression
    data = yaml.safe_load((project / "evalkit.yaml").read_text(encoding="utf-8"))
    data["autonomy"] = {"max_level": 3, "apply_perimeter": ["apply_fix_low_risk"]}
    (project / "evalkit.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    res = RetrofitCycle(repo, actor="test").run(
        project, "greeter", broken_campaign_id=broken, good_campaign_id=good
    )
    assert res.decision == "APPLY_ALLOWED"
    # a decided ticket is never reworked by a second cycle
    again = RetrofitCycle(repo, actor="test").run(
        project, "greeter", broken_campaign_id=broken, good_campaign_id=good
    )
    assert again.decision == "ALREADY_DECIDED" and again.ticket_id == res.ticket_id


def test_retrofit_agent_actor_never_applies(
    repo: SQLiteRepository, project: Path, regression: tuple[str, str]
) -> None:
    good, broken = regression
    data = yaml.safe_load((project / "evalkit.yaml").read_text(encoding="utf-8"))
    data["autonomy"] = {"max_level": 3, "apply_perimeter": ["apply_fix_low_risk"]}
    (project / "evalkit.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    res = RetrofitCycle(repo, actor="agent:greeter").run(
        project, "greeter", broken_campaign_id=broken, good_campaign_id=good
    )
    assert res.decision == "HUMAN_VALIDATION_REQUIRED" and "never apply" in res.rationale


def test_retrofit_rejects_fix_that_does_not_help(
    repo: SQLiteRepository, project: Path, regression: tuple[str, str]
) -> None:
    good, broken = regression
    still_wrong = params_override({"behavior": "wrong"}, version="1.1.1")
    res = RetrofitCycle(repo, actor="test", fix_provider=still_wrong, max_iterations=1).run(
        project, "greeter", broken_campaign_id=broken, good_campaign_id=good
    )
    assert res.decision == "REJECTED" and res.learning_id is None
    assert repo.get_ticket(res.ticket_id).status is TicketStatus.REJECTED
    assert LearningStore(repo).list("demo") == []


def test_retrofit_nothing_to_fix(repo: SQLiteRepository, project: Path) -> None:
    a = _run(repo, project, "greeter")
    b = _run(repo, project, "greeter", baseline_campaign_id=a.campaign_id)
    res = RetrofitCycle(repo).run(
        project, "greeter", broken_campaign_id=b.campaign_id, good_campaign_id=a.campaign_id
    )
    assert res.decision == "NOTHING_TO_FIX" and res.ticket_id == ""


def test_retrofit_confirm_promotes_learning_on_holdout(
    repo: SQLiteRepository, project: Path, regression: tuple[str, str], demo_dir: Path
) -> None:
    good, broken = regression
    res = RetrofitCycle(repo, actor="test").run(
        project, "greeter", broken_campaign_id=broken, good_campaign_id=good
    )
    assert res.learning_id
    shutil.copy(demo_dir / "evalkit.yaml", project / "evalkit.yaml")  # human applies the fix
    out = RetrofitCycle(repo, actor="human").confirm(
        project, "greeter", good_campaign_id=good, learning_id=res.learning_id
    )
    assert out["learning_status"] == "verified" and out["regressions"] == []
    runs = list(repo.list_runs(out["campaign_id"]))
    assert any(r.scenario_id == "demo.greet.h01" for r in runs), "DEEP includes HOLDOUT"
    learning = LearningStore(repo).get(res.learning_id)
    assert learning["status"] == "verified" and out["campaign_id"] in learning["evidence_refs"]
    with pytest.raises(ValueError, match="unknown learning status"):
        LearningStore(repo).set_status(res.learning_id, "law")
    assert "verified" in LearningStore(repo).render_markdown("demo")


# --- self-evaluation (scenario 21) ---------------------------------------------------------


def test_self_evaluation_passes_and_persists(repo: SQLiteRepository) -> None:
    card, details = self_evaluate(repo)
    names = {n for n, _, _ in details}
    assert names >= {"statistics", "token_accounting", "cost_computation", "budget_enforcement"}
    assert card.overall_status is EvalStatus.PASS, details
    assert card.agent_id == "evalkit" and card.project_id == "evalkit-self"
    assert repo.scorecard_for_campaign(card.campaign_id) is not None


def test_self_evaluation_reports_failed_check(
    repo: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    from evalkit.improvement import self_eval

    broken = [(d, n, fn) for d, n, fn in self_eval.CHECKS]
    broken[0] = (broken[0][0], "statistics", lambda _r: (False, "forced failure"))
    monkeypatch.setattr(self_eval, "CHECKS", broken)
    card, details = self_evaluate(repo, persist=False)
    assert card.overall_status is EvalStatus.FAIL and "statistics" in card.eliminatory_failures
    assert ("statistics", False, "forced failure") in details


# --- CLI -----------------------------------------------------------------------------------


def test_cli_phase6_commands(tmp_path: Path, project: Path) -> None:
    data = str(tmp_path / "data")
    ok = runner_cli.invoke(app, ["run", str(project), "--agent", "greeter", "--data-dir", data])
    assert ok.exit_code == 0, ok.output
    _set_agent(project, "greeter", BROKEN_GREETER)
    ko = runner_cli.invoke(app, ["run", str(project), "--agent", "greeter", "--data-dir", data])
    assert ko.exit_code in (0, 1), ko.output
    lst = runner_cli.invoke(app, ["campaigns", "--project", "demo", "--data-dir", data])
    ids = [line.split()[0] for line in lst.output.splitlines() if line.startswith("cmp_")]
    good, broken = ids[0], ids[1]

    det = runner_cli.invoke(app, ["tickets", "detect", broken, "--data-dir", data])
    assert det.exit_code == 0 and "tck_" in det.output, det.output
    rf = runner_cli.invoke(
        app,
        [
            "retrofit",
            "run",
            "--project-dir",
            str(project),
            "--agent",
            "greeter",
            "--broken",
            broken,
            "--good",
            good,
            "--data-dir",
            data,
        ],
    )
    assert rf.exit_code == 0 and "HUMAN_VALIDATION_REQUIRED" in rf.output, rf.output
    assert "LEARN" in rf.output
    assert (
        "lrn_"
        in runner_cli.invoke(
            app, ["learnings", "list", "--project", "demo", "--data-dir", data]
        ).output
    )
    tl = runner_cli.invoke(app, ["tickets", "list", "--project", "demo", "--data-dir", data])
    assert "VALIDATED" in tl.output
    tid = next(line.split()[0] for line in tl.output.splitlines() if " OPEN " in line)
    bad = runner_cli.invoke(
        app, ["tickets", "transition", tid, "VALIDATED", "--note", "x", "--data-dir", data]
    )
    assert bad.exit_code == 2
    out_md = tmp_path / "BACKLOG.md"
    exp = runner_cli.invoke(
        app, ["backlog", "export", "--project", "demo", "--out", str(out_md), "--data-dir", data]
    )
    assert exp.exit_code == 0 and out_md.read_text(encoding="utf-8").startswith("# Backlog")
    lrn_md = tmp_path / "LEARNINGS.md"
    runner_cli.invoke(
        app, ["learnings", "export", "--project", "demo", "--out", str(lrn_md), "--data-dir", data]
    )
    assert "observed" in lrn_md.read_text(encoding="utf-8")
    sc = runner_cli.invoke(app, ["self-check", "--data-dir", data])
    assert sc.exit_code == 0 and "PASS" in sc.output, sc.output
