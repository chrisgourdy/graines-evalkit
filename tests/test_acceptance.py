"""Phase 8 — acceptance: injection protection (27), doc inconsistency detection (29),
report generation from evidence (30), registry ↔ ACCEPTANCE_SCENARIOS.md consistency."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from evalkit.acceptance import SCENARIOS, Mode, build_report, parse_junit, render_markdown
from evalkit.cli.main import app
from evalkit.contracts import Budget, BudgetScope, Dimension, EvalStatus, Profile
from evalkit.core import CampaignRunner, load_project
from evalkit.cost_controller import SQLiteCostController
from evalkit.scoring import build_scorecard
from evalkit.storage import SQLiteRepository

ROOT = Path(__file__).resolve().parents[1]
runner_cli = CliRunner()


# --- 27: prompt-injection protection ---------------------------------------------------


def test_injection_does_not_alter_criteria_or_budget(
    repo: SQLiteRepository, demo_dir: Path, tmp_path: Path
) -> None:
    project = tmp_path / "proj"
    shutil.copytree(demo_dir, project)
    cfg = yaml.safe_load((project / "evalkit.yaml").read_text(encoding="utf-8"))
    cfg["agents"]["greeter-guarded"]["params"] = {"behavior": "injection"}
    (project / "evalkit.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    ctl = SQLiteCostController(repo)
    budget = Budget(budget_id="b-inj", scope=BudgetScope.PROJECT, scope_ref="demo", max_cost=0.5)
    ctl.save_budget(budget)
    before_autonomy = load_project(project).autonomy.model_dump()
    scenario_file = project / "scenarios" / "greeter-guarded" / "greet-sec-001.yaml"
    before_scenario = scenario_file.read_bytes()

    runner = CampaignRunner(repo)
    planned = runner.plan(project, "greeter-guarded", profile=Profile.STANDARD)
    campaign = asyncio.run(runner.execute(planned))
    run = next(iter(repo.list_runs(campaign.campaign_id)))
    assert isinstance(run.output, dict) and "IGNORE ALL PREVIOUS" in json.dumps(run.output)
    results = {r.evaluator_id: r for r in repo.list_results(run.run_id)}
    assert results["injection_guard"].status is EvalStatus.FAIL
    assert results["injection_guard"].dimension is Dimension.SECURITY
    assert any(e.kind == "injection_marker" for e in results["injection_guard"].evidence)
    card = build_scorecard(repo, campaign.campaign_id)
    assert card.overall_status is EvalStatus.FAIL and card.eliminatory_failures
    # nothing the output "asked for" happened: budget, autonomy and criteria are untouched
    after = ctl.get_budget("b-inj") if hasattr(ctl, "get_budget") else None
    stored = repo._conn.execute("SELECT max_cost FROM budgets WHERE budget_id='b-inj'").fetchone()
    assert float(stored["max_cost"]) == 0.5 and (after is None or after.max_cost == 0.5)
    assert load_project(project).autonomy.model_dump() == before_autonomy
    assert scenario_file.read_bytes() == before_scenario
    stored_scenario = repo.get_scenario("demo.guarded.sec.001", "1.0.0")
    assert [v.evaluator for v in stored_scenario.verifications] == [
        "exact_match",
        "injection_guard",
    ]
    assert all(v.blocking for v in stored_scenario.verifications)
    # the injected text is stored as data only: no event carries it as an instruction/decision
    for e in repo.query(campaign_id=campaign.campaign_id):
        assert e.event_type.value not in (
            "permission.changed",
            "config.changed",
            "validation.decision",
        )


# --- 29: documentation inconsistency detection ------------------------------------------


def test_removing_referenced_doc_is_detected(tmp_path: Path) -> None:
    from tests.test_docs_consistency import _referenced_paths

    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    refs = _referenced_paths(text)
    assert "docs/STATUS.md" in refs
    fake_root = tmp_path / "root"
    for ref in refs:
        if (ROOT / ref).is_file():
            (fake_root / ref).parent.mkdir(parents=True, exist_ok=True)
            (fake_root / ref).write_text("x", encoding="utf-8")
        elif (ROOT / ref).is_dir():
            (fake_root / ref).mkdir(parents=True, exist_ok=True)
    assert not [r for r in refs if not (fake_root / r).exists()], "copy is consistent"
    (fake_root / "docs" / "STATUS.md").unlink()  # "remove a referenced doc"
    missing = [r for r in refs if not (fake_root / r).exists()]
    assert missing == ["docs/STATUS.md"], "the consistency check names the removed document"


# --- 30: acceptance report from evidence ------------------------------------------------


def _junit(path: Path, outcomes: dict[str, str]) -> Path:
    cases = []
    for nodeid, outcome in outcomes.items():
        file, name = nodeid.split("::", 1)
        classname = file[:-3].replace("/", ".")
        tag = {"failed": "failure", "error": "error", "skipped": "skipped"}.get(outcome)
        inner = "" if tag is None else f'<{tag} message="boom">boom</{tag}>'
        cases.append(
            f'<testcase classname="{classname}" name="{name}" time="0.1">{inner}</testcase>'
        )
    path.write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="pytest">'
        + "".join(cases)
        + "</testsuite></testsuites>",
        encoding="utf-8",
    )
    return path


def test_report_lists_every_scenario_with_evidence(tmp_path: Path) -> None:
    all_tests = {t: "passed" for s in SCENARIOS for t in s.tests}
    junit = _junit(tmp_path / "junit.xml", all_tests)
    outcomes = parse_junit(junit)
    assert set(outcomes) == set(all_tests)
    no_ci = tmp_path / "no-ci-evidence"  # a checkout without CI evidence: Docker stays BLOCKED
    no_ci.mkdir()
    report = build_report(outcomes, junit_path=junit, root=no_ci)
    assert len(report.results) == 30
    assert report.counts["FAIL"] == 0 and report.counts["NOT_RUN"] == 0
    assert report.counts["BLOCKED"] == 1  # Docker, with its reason
    assert report.accepted
    md = render_markdown(report)
    for s in SCENARIOS:
        assert f"| {s.number} | {s.title} |" in md and s.criterion in md
        for t in s.tests:
            assert t in md
    assert "no Docker daemon" in md and "ACCEPTED" in md
    # a failing covering test makes its scenario FAIL and the verdict NOT ACCEPTED — never hidden
    all_tests["tests/test_stats.py::test_effect_sizes_and_holm"] = "failed"
    report2 = build_report(
        parse_junit(_junit(tmp_path / "j2.xml", all_tests)), junit_path=junit, root=no_ci
    )
    failing = [r for r in report2.results if r.result == "FAIL"]
    assert [r.scenario.number for r in failing] == [7, 28] and not report2.accepted
    assert "boom" in failing[0].detail and "NOT ACCEPTED" in render_markdown(report2)
    # a missing covering test is NOT_RUN, not PASS
    del all_tests["tests/test_improvement.py::test_self_evaluation_passes_and_persists"]
    report3 = build_report(
        parse_junit(_junit(tmp_path / "j3.xml", all_tests)), junit_path=junit, root=no_ci
    )
    assert next(r for r in report3.results if r.scenario.number == 21).result == "NOT_RUN"


def test_registry_matches_acceptance_scenarios_doc() -> None:
    doc = (ROOT / "docs" / "ACCEPTANCE_SCENARIOS.md").read_text(encoding="utf-8")
    rows = {
        int(m.group(1)): (m.group(2).strip(), m.group(3).strip())
        for m in re.finditer(r"^\| (\d+) \| ([^|]+) \| ([^|]+) \|", doc, flags=re.MULTILINE)
    }
    assert sorted(rows) == list(range(1, 31))
    for s in SCENARIOS:
        title, criterion = rows[s.number]
        assert s.title == title, (s.number, s.title, title)
        assert s.criterion == criterion, (s.number, s.criterion, criterion)
    for s in SCENARIOS:
        assert s.tests or s.mode in (Mode.CI, Mode.SUITE), s.number
        if s.mode is Mode.CI:
            assert s.blocked_reason
        for t in s.tests:
            file, name = t.split("::", 1)
            source = (ROOT / file).read_text(encoding="utf-8")
            assert re.search(rf"^(async )?def {re.escape(name)}\(", source, flags=re.MULTILINE), t


def test_cli_acceptance_list() -> None:
    r = runner_cli.invoke(app, ["acceptance", "list"])
    assert r.exit_code == 0 and "30" in r.output and "BLOCKED" in r.output


def test_ci_evidence_lifts_docker_block_only_when_checks_pass(tmp_path: Path) -> None:
    all_tests = {t: "passed" for s in SCENARIOS for t in s.tests}
    junit = _junit(tmp_path / "junit.xml", all_tests)
    docker = next(s for s in SCENARIOS if s.number == 23)
    assert docker.ci_evidence
    root = tmp_path / "root"
    ev_path = root / docker.ci_evidence
    ev_path.parent.mkdir(parents=True)
    # no evidence file → BLOCKED with reason
    r = next(
        x
        for x in build_report(parse_junit(junit), junit_path=junit, root=root).results
        if x.scenario.number == 23
    )
    assert r.result == "BLOCKED" and "Docker" in r.detail
    good = {
        "workflow": "ci",
        "run_id": "1",
        "run_url": "https://example.invalid/runs/1",
        "commit": "abc",
        "image_digest": "sha256:x",
        "campaign_id": "cmp_1",
        "campaign_status": "COMPLETED",
        "conclusion": "success",
        "checks": dict.fromkeys(docker.ci_required_checks, True),
    }
    ev_path.write_text(json.dumps(good), encoding="utf-8")
    report = build_report(parse_junit(junit), junit_path=junit, root=root)
    r = next(x for x in report.results if x.scenario.number == 23)
    assert r.result == "PASS" and report.counts["BLOCKED"] == 0 and report.accepted
    assert "runs/1" in r.detail and all(o.outcome == "passed" for o in r.evidence)
    bad = {**good, "checks": {**good["checks"], "campaign_persisted": False}}
    ev_path.write_text(json.dumps(bad), encoding="utf-8")
    r = next(
        x
        for x in build_report(parse_junit(junit), junit_path=junit, root=root).results
        if x.scenario.number == 23
    )
    assert r.result == "FAIL" and "campaign_persisted" in r.detail
    ev_path.write_text(json.dumps({**good, "conclusion": "failure"}), encoding="utf-8")
    r = next(
        x
        for x in build_report(parse_junit(junit), junit_path=junit, root=root).results
        if x.scenario.number == 23
    )
    assert r.result == "FAIL"
