"""SCORING_ENGINE rules, HTML/CSV reporting and dashboard — all from stored data."""

from __future__ import annotations

import asyncio
import csv
import re
from pathlib import Path

from typer.testing import CliRunner

from evalkit.cli.main import app
from evalkit.contracts import Dimension, EvalStatus, EventType, MeasurementKind, Profile
from evalkit.core import CampaignRunner
from evalkit.reporting import build_dashboard, export_campaign_csv, render_campaign_html
from evalkit.reporting.svg import Bar, bar_chart, histogram, line_chart, stacked_bars
from evalkit.scoring import build_scorecard
from evalkit.storage import SQLiteRepository


def _run(repo: SQLiteRepository, demo_dir: Path, agent: str, profile: Profile, **kw: object):  # type: ignore[no-untyped-def]
    runner = CampaignRunner(repo)
    return asyncio.run(runner.execute(runner.plan(demo_dir, agent, profile=profile, **kw)))  # type: ignore[arg-type]


def test_scorecard_compliant_agent(repo: SQLiteRepository, demo_dir: Path) -> None:
    camp = _run(repo, demo_dir, "greeter", Profile.STANDARD)
    card = build_scorecard(repo, camp.campaign_id)
    assert card.overall_status is EvalStatus.PASS
    assert card.eliminatory_failures == [] and card.regressions == []
    assert {d.dimension for d in card.dimensions} >= {Dimension.ACCURACY, Dimension.FORMAT}
    assert all(d.measurement is MeasurementKind.OBJECTIVE for d in card.dimensions)
    assert all(d.ci and d.ci.method in ("wilson", "clopper_pearson") for d in card.dimensions)
    assert any("underpowered" in w for w in card.validity_warnings)  # n=1 per dimension: honest
    assert card.aggregate_score is None and card.aggregate_formula is None
    assert repo.scorecard_for_campaign(camp.campaign_id) is not None
    assert card.cost_status == "MEASURED" or card.cost_status == "UNKNOWN"


def test_scorecard_eliminatory_failure_is_independent_of_aggregate(
    repo: SQLiteRepository, demo_dir: Path
) -> None:
    camp = _run(repo, demo_dir, "greeter-wrong", Profile.STANDARD)
    weights = {
        "accuracy": 1.0,
        "constraints": 1.0,
        "format": 1.0,
        "completeness": 1.0,
        "tool_use": 1.0,
    }
    card = build_scorecard(repo, camp.campaign_id, weights=weights)
    assert card.overall_status is EvalStatus.FAIL and card.eliminatory_failures
    assert card.aggregate_score is not None and card.aggregate_formula
    assert "NOT absorbed" in card.aggregate_formula
    acc = next(d for d in card.dimensions if d.dimension is Dimension.ACCURACY)
    assert acc.status is EvalStatus.FAIL
    # missing dimensions listed and excluded from the aggregate formula
    card2 = build_scorecard(
        repo, camp.campaign_id, weights={"accuracy": 1.0, "security": 2.0}, persist=False
    )
    assert "security" not in (card2.aggregate_formula or "").split("/")[0]


def test_scorecard_coverage_and_required_dimension(repo: SQLiteRepository, demo_dir: Path) -> None:
    camp = _run(
        repo, demo_dir, "greeter", Profile.QUICK
    )  # greet-002 (MEDIUM) and h01 (HIGH, holdout) not run
    card = build_scorecard(
        repo, camp.campaign_id, required_dimensions={Dimension.SECURITY}, persist=False
    )
    assert card.overall_status is EvalStatus.INCONCLUSIVE  # required dimension never evaluated
    assert any("coverage" in w and "demo.greet.h01" in w for w in card.validity_warnings)


def test_scorecard_regression_and_overfitting_signal(
    repo: SQLiteRepository, demo_dir: Path
) -> None:
    base = _run(repo, demo_dir, "greeter-flaky", Profile.DEEP, seed=11)
    cand = _run(
        repo,
        demo_dir,
        "greeter-flaky",
        Profile.DEEP,
        seed=12,
        baseline_campaign_id=base.campaign_id,
    )
    card = build_scorecard(repo, cand.campaign_id)
    assert card.baseline_campaign_id == base.campaign_id
    # with 2 paired scenarios the campaign-level comparison must be inconclusive, never a verdict
    assert any("inconclusive" in w for w in card.validity_warnings)
    types = [e.event_type for e in repo.query(campaign_id=cand.campaign_id)]
    if card.regressions:
        assert EventType.REGRESSION_DETECTED in types
    # non-equivalent profiles are flagged
    other = _run(
        repo,
        demo_dir,
        "greeter-flaky",
        Profile.STANDARD,
        seed=13,
        baseline_campaign_id=base.campaign_id,
    )
    card2 = build_scorecard(repo, other.campaign_id, persist=False)
    assert any("non-equivalent" in w for w in card2.validity_warnings)


def test_html_report_values_come_from_store(repo: SQLiteRepository, demo_dir: Path) -> None:
    camp = _run(repo, demo_dir, "greeter-flaky", Profile.DEEP, seed=5)
    card = build_scorecard(repo, camp.campaign_id)
    html = render_campaign_html(repo, camp.campaign_id)
    assert "<script" not in html and "http" not in html.split("<style>")[1].split("</style>")[0]
    assert "<svg" in html and card.overall_status.value in html
    for d in card.dimensions:
        if d.pass_rate is not None:
            assert f"{d.pass_rate:.0%}" in html
    runs = list(repo.list_runs(camp.campaign_id))
    assert f"of {len(runs)}" in html
    assert "not a production validation" in html
    # no truncated axes: every bar chart axis starts at 0
    assert re.search(r">0%<", html) is not None


def test_csv_exports(repo: SQLiteRepository, demo_dir: Path, tmp_path: Path) -> None:
    camp = _run(repo, demo_dir, "greeter", Profile.STANDARD)
    paths = export_campaign_csv(repo, camp.campaign_id, tmp_path)
    assert [p.suffix for p in paths] == [".csv"] * 3
    runs_rows = list(csv.DictReader(paths[0].open()))
    assert len(runs_rows) == len(list(repo.list_runs(camp.campaign_id)))
    results_rows = list(csv.DictReader(paths[1].open()))
    assert {r["status"] for r in results_rows} <= {
        "PASS",
        "FAIL",
        "WARNING",
        "INCONCLUSIVE",
        "NOT_EVALUATED",
    }
    usage_rows = list(csv.DictReader(paths[2].open()))
    assert usage_rows and all(
        r["source"] in ("REPORTED", "ESTIMATED", "UNKNOWN") for r in usage_rows
    )


def test_dashboard_pages(repo: SQLiteRepository, demo_dir: Path, tmp_path: Path) -> None:
    _run(repo, demo_dir, "greeter", Profile.STANDARD)
    _run(repo, demo_dir, "greeter-wrong", Profile.QUICK)
    dry = _run(repo, demo_dir, "greeter-flaky", Profile.DEEP, dry_run=True)
    pages = build_dashboard(repo, "demo", tmp_path / "dash")
    names = {p.name for p in pages}
    assert {
        "index.html",
        "finances.html",
        "improvement.html",
        "agent-greeter.html",
        "agent-greeter-wrong.html",
    } <= names
    assert f"campaign-{dry.campaign_id}.html" not in names  # dry runs have nothing to score
    index = (tmp_path / "dash" / "index.html").read_text()
    assert "PASS" in index and "FAIL" in index and "greeter-wrong" in index
    assert (tmp_path / "dash" / "improvement.html").read_text().count("No ticket stored yet") == 1
    fin = (tmp_path / "dash" / "finances.html").read_text()
    assert "sim/sim-deterministic-1" in fin


def test_svg_helpers_handle_edge_cases() -> None:
    svg = bar_chart(
        [Bar("a", None), Bar("b", 0.5, 0.2, 0.8)], title="t", max_value=1.0, percent=True
    )
    assert "n/a" in svg and "50%" in svg and svg.count("<line") >= 3
    assert "no data" in histogram([], title="h")
    assert "<polyline" in line_chart(
        [("s", [0.1, 0.2, None, 0.4])], ["a", "b", "c", "d"], title="l"
    )
    stacked = stacked_bars([("x", {"in": 10, "out": 0})], ["in", "out"], title="s")
    assert ">in<" in stacked and ">out<" not in stacked  # absent categories are not in the legend
    assert "&lt;" in bar_chart([Bar("<b>", 1.0)], title="<t>")  # labels are escaped


def test_cli_scorecard_and_dashboard(demo_dir: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    data = str(tmp_path / "d")
    res = runner.invoke(
        app, ["run", str(demo_dir), "--agent", "greeter", "--data-dir", data, "-p", "quick"]
    )
    assert res.exit_code == 0, res.output
    assert "scorecard: PASS" in res.output and ".html" in res.output
    cid = res.output.split()[1]
    res = runner.invoke(app, ["scorecard", cid, "--data-dir", data, "--project-dir", str(demo_dir)])
    assert res.exit_code == 0 and "accuracy" in res.output
    res = runner.invoke(
        app,
        [
            "dashboard",
            "build",
            "--project",
            "demo",
            "--data-dir",
            data,
            "--out",
            str(tmp_path / "dash"),
        ],
    )
    assert res.exit_code == 0 and (tmp_path / "dash" / "index.html").is_file()
    res = runner.invoke(app, ["report", cid, "--data-dir", data])
    assert res.exit_code == 0 and ".usage.csv" in res.output
