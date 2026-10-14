"""End-to-end campaign cycle on the demo project, without any provider."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from evalkit.cli.main import app
from evalkit.contracts import CampaignStatus, EvalStatus, EventType, Profile, RunStatus
from evalkit.core import (
    CampaignRefusedError,
    CampaignRunner,
    ScenarioLoadError,
    load_project,
    load_scenarios,
)
from evalkit.reporting import build_report, write_report
from evalkit.storage import SQLiteRepository


def test_demo_project_loads(demo_dir: Path) -> None:
    config = load_project(demo_dir)
    scenarios = load_scenarios(demo_dir, config)
    assert config.project_id == "demo"
    assert {s.agent_id for s in scenarios} == set(config.agents)
    assert any(s.dataset.value == "HOLDOUT" for s in scenarios)


def test_invalid_scenario_is_loud(tmp_path: Path) -> None:
    (tmp_path / "evalkit.yaml").write_text(
        "project_id: p\nagents: {a: {adapter: sim.deterministic, version: '1'}}\n"
    )
    (tmp_path / "scenarios").mkdir()
    (tmp_path / "scenarios" / "bad.yaml").write_text("scenario_id: p.bad\nversion: 1.0\n")
    with pytest.raises(ScenarioLoadError, match=r"bad\.yaml"):
        load_scenarios(tmp_path, load_project(tmp_path))


def test_compliant_agent_passes(repo: SQLiteRepository, demo_dir: Path) -> None:
    runner = CampaignRunner(repo)
    planned = runner.plan(demo_dir, "greeter", profile=Profile.STANDARD)
    assert planned.planned_runs == 2  # deterministic → repetitions collapsed
    campaign = asyncio.run(runner.execute(planned))
    assert campaign.status is CampaignStatus.COMPLETED
    report = build_report(repo, campaign.campaign_id)
    assert report["overall_status"] == "PASS"
    assert report["eliminatory_failures"] == []
    assert report["usage"]["status"] == "REPORTED"
    runs = list(repo.list_runs(campaign.campaign_id))
    assert all(r.status is RunStatus.COMPLETED and r.output_ref for r in runs)
    assert all(r.trajectory and r.trajectory.completed for r in runs)


def test_incorrect_agent_fails_with_evidence(repo: SQLiteRepository, demo_dir: Path) -> None:
    runner = CampaignRunner(repo)
    campaign = asyncio.run(
        runner.execute(runner.plan(demo_dir, "greeter-wrong", profile=Profile.STANDARD))
    )
    report = build_report(repo, campaign.campaign_id)
    assert report["overall_status"] == "FAIL"
    assert report["eliminatory_failures"]
    results = [
        res for r in repo.list_runs(campaign.campaign_id) for res in repo.list_results(r.run_id)
    ]
    failed = [r for r in results if r.status is EvalStatus.FAIL]
    assert failed and all(r.evidence for r in failed if r.evaluator_id == "exact_match")


def test_profiles_select_scenarios(repo: SQLiteRepository, demo_dir: Path) -> None:
    runner = CampaignRunner(repo)
    quick = runner.plan(demo_dir, "greeter", profile=Profile.QUICK)
    standard = runner.plan(demo_dir, "greeter", profile=Profile.STANDARD)
    deep = runner.plan(demo_dir, "greeter", profile=Profile.DEEP)
    assert [s.scenario_id for s in quick.scenarios] == ["demo.greet.001"]
    assert "demo.greet.h01" not in standard.campaign.scenario_ids
    assert "demo.greet.h01" in deep.campaign.scenario_ids
    flaky = runner.plan(demo_dir, "greeter-flaky", profile=Profile.DEEP)
    assert all(v >= 3 for v in flaky.repetitions.values())


def test_dry_run_makes_no_call(repo: SQLiteRepository, demo_dir: Path) -> None:
    runner = CampaignRunner(repo)
    planned = runner.plan(demo_dir, "greeter-flaky", profile=Profile.DEEP, dry_run=True)
    campaign = asyncio.run(runner.execute(planned))
    assert campaign.status is CampaignStatus.DRY_RUN
    assert list(repo.list_runs(campaign.campaign_id)) == []
    types = [e.event_type for e in repo.query(campaign_id=campaign.campaign_id)]
    assert EventType.AGENT_CALLED not in types


def test_stochastic_campaign_is_seed_reproducible(repo: SQLiteRepository, demo_dir: Path) -> None:
    runner = CampaignRunner(repo)
    c1 = asyncio.run(
        runner.execute(runner.plan(demo_dir, "greeter-flaky", profile=Profile.DEEP, seed=7))
    )
    c2 = asyncio.run(
        runner.execute(runner.plan(demo_dir, "greeter-flaky", profile=Profile.DEEP, seed=7))
    )
    o1 = [
        (r.scenario_id, r.attempt, json.dumps(r.output, sort_keys=True), r.error)
        for r in repo.list_runs(c1.campaign_id)
    ]
    o2 = [
        (r.scenario_id, r.attempt, json.dumps(r.output, sort_keys=True), r.error)
        for r in repo.list_runs(c2.campaign_id)
    ]
    assert o1 == o2
    c3 = asyncio.run(
        runner.execute(runner.plan(demo_dir, "greeter-flaky", profile=Profile.DEEP, seed=8))
    )
    o3 = [
        (r.scenario_id, r.attempt, json.dumps(r.output, sort_keys=True), r.error)
        for r in repo.list_runs(c3.campaign_id)
    ]
    assert o1 != o3


def test_stop_on_eliminatory(repo: SQLiteRepository, demo_dir: Path) -> None:
    runner = CampaignRunner(repo, stop_on_eliminatory=True)
    campaign = asyncio.run(
        runner.execute(runner.plan(demo_dir, "greeter-wrong", profile=Profile.STANDARD))
    )
    assert campaign.status is CampaignStatus.STOPPED_ELIMINATORY
    assert len(list(repo.list_runs(campaign.campaign_id))) == 1


def test_cost_bearing_adapter_refused_without_cost_controller(
    repo: SQLiteRepository, tmp_path: Path, demo_dir: Path
) -> None:
    (tmp_path / "evalkit.yaml").write_text(
        "project_id: demo\nagents:\n  paid:\n    adapter: python.callable\n    version: '1'\n"
        "    params: {target: 'json:dumps', cost_bearing: true}\n"
    )
    (tmp_path / "scenarios").mkdir()
    src = (
        (demo_dir / "scenarios" / "greeter" / "greet-001.yaml")
        .read_text()
        .replace("agent_id: greeter", "agent_id: paid")
    )
    (tmp_path / "scenarios" / "s.yaml").write_text(src)
    runner = CampaignRunner(repo)
    with pytest.raises(CampaignRefusedError, match="COST_CONTROLLER"):
        runner.plan(tmp_path, "paid", profile=Profile.STANDARD)
    assert runner.plan(tmp_path, "paid", profile=Profile.STANDARD, dry_run=True).campaign.dry_run


def test_audit_chronology_reconstructs_campaign(repo: SQLiteRepository, demo_dir: Path) -> None:
    runner = CampaignRunner(repo)
    campaign = asyncio.run(
        runner.execute(runner.plan(demo_dir, "greeter", profile=Profile.STANDARD))
    )
    events = list(repo.query(campaign_id=campaign.campaign_id))
    seqs = [e.sequence for e in events]
    assert seqs == sorted(seqs) and None not in seqs
    assert events[0].event_type is EventType.CAMPAIGN_STARTED
    assert events[-1].event_type is EventType.CAMPAIGN_ENDED
    per_run: dict[str, list[EventType]] = {}
    for e in events:
        if e.run_id:
            per_run.setdefault(e.run_id, []).append(e.event_type)
    assert per_run and all(
        kinds[0] is EventType.AGENT_CALLED and EventType.EVALUATION_RESULT in kinds
        for kinds in per_run.values()
    )
    assert any(e.event_type is EventType.TOOL_CALLED for e in events)  # greeter declares a tool
    assert any(e.event_type is EventType.USAGE_RECORDED and e.usage for e in events)
    ok, _ = repo.verify_chain()
    assert ok


def test_two_projects_are_isolated(repo: SQLiteRepository, demo_dir: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    (other / "scenarios").mkdir(parents=True)
    (other / "evalkit.yaml").write_text(
        "project_id: other\nagents: {other-g: {adapter: sim.deterministic, version: '2'}}\n"
    )
    src = (demo_dir / "scenarios" / "greeter" / "greet-001.yaml").read_text()
    (other / "scenarios" / "s.yaml").write_text(
        src.replace("project_id: demo", "project_id: other")
        .replace("agent_id: greeter", "agent_id: other-g")
        .replace("scenario_id: demo.greet.001", "scenario_id: other.greet.001")
    )
    runner = CampaignRunner(repo)
    c1 = asyncio.run(runner.execute(runner.plan(demo_dir, "greeter", profile=Profile.QUICK)))
    c2 = asyncio.run(runner.execute(runner.plan(other, "other-g", profile=Profile.QUICK)))
    assert [c.campaign_id for c in repo.list_campaigns("demo")] == [c1.campaign_id]
    assert [c.campaign_id for c in repo.list_campaigns("other")] == [c2.campaign_id]
    assert all(e.project_id == "other" for e in repo.query(campaign_id=c2.campaign_id))


def test_report_files_written(repo: SQLiteRepository, demo_dir: Path, tmp_path: Path) -> None:
    runner = CampaignRunner(repo)
    campaign = asyncio.run(
        runner.execute(runner.plan(demo_dir, "greeter", profile=Profile.STANDARD))
    )
    json_path, md_path = write_report(repo, campaign.campaign_id, tmp_path / "reports")
    data = json.loads(json_path.read_text())
    assert data["campaign"]["campaign_id"] == campaign.campaign_id
    assert data["dimensions"]["accuracy"]["ci"] is None
    md = md_path.read_text()
    assert "Validity limits" in md and "not a production validation" in md


def test_cli_run_report_check(demo_dir: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    data = str(tmp_path / "data")
    res = runner.invoke(
        app, ["run", str(demo_dir), "--agent", "greeter", "--data-dir", data, "-p", "quick"]
    )
    assert res.exit_code == 0, res.output
    assert "status: COMPLETED" in res.output and "report:" in res.output
    campaign_id = res.output.split()[1]
    res = runner.invoke(app, ["report", campaign_id, "--data-dir", data])
    assert res.exit_code == 0, res.output
    res = runner.invoke(app, ["db", "check", "--data-dir", data])
    assert res.exit_code == 0 and "audit chain: OK" in res.output
    res = runner.invoke(app, ["campaigns", "--project", "demo", "--data-dir", data])
    assert campaign_id in res.output
    res = runner.invoke(app, ["run", str(demo_dir), "--agent", "nope", "--data-dir", data])
    assert res.exit_code == 2
    res = runner.invoke(app, ["scenarios", "validate", str(demo_dir)])
    assert res.exit_code == 0 and "7 scenario(s)" in res.output
