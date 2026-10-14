"""``evalkit`` command-line interface — thin layer over ``evalkit.core``."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import typer

from evalkit import __version__
from evalkit.contracts import Profile

app = typer.Typer(no_args_is_help=True, help="EVALKIT — evaluate, meter and improve AI agents.")
db_app = typer.Typer(no_args_is_help=True, help="Database maintenance.")
scenarios_app = typer.Typer(no_args_is_help=True, help="Scenario tooling.")
budget_app = typer.Typer(no_args_is_help=True, help="Budgets (COST_CONTROLLER).")
prices_app = typer.Typer(no_args_is_help=True, help="Price registry.")
app.add_typer(db_app, name="db")
app.add_typer(scenarios_app, name="scenarios")
app.add_typer(budget_app, name="budget")
app.add_typer(prices_app, name="prices")


def _data_dir(value: Path | None) -> Path:
    return value or Path(os.environ.get("EVALKIT_DATA_DIR", "data"))


def _repo(data_dir: Path | None):  # type: ignore[no-untyped-def]  # noqa: ANN202
    from evalkit.storage import SQLiteRepository

    repo = SQLiteRepository(_data_dir(data_dir))
    repo.migrate()
    return repo


@app.command()
def version() -> None:
    """Print EVALKIT version and contract schema version."""
    from evalkit.contracts import CONTRACT_SCHEMA_VERSION

    typer.echo(f"evalkit {__version__} (contracts {CONTRACT_SCHEMA_VERSION})")


@app.command("export-schemas")
def export_schemas(out: Path = typer.Option(Path("schemas"), help="Output directory.")) -> None:
    """Export JSON Schemas of public contracts (source of the TypeScript SDK types)."""
    from evalkit.contracts import export_json_schemas

    for path in export_json_schemas(out):
        typer.echo(str(path))


@scenarios_app.command("validate")
def scenarios_validate(project_dir: Path = typer.Argument(..., exists=True)) -> None:
    """Validate evalkit.yaml and every scenario file of a project."""
    from evalkit.core import ScenarioLoadError, load_project, load_scenarios

    try:
        config = load_project(project_dir)
        scenarios = load_scenarios(project_dir, config)
    except ScenarioLoadError as exc:
        typer.echo(f"INVALID: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"OK: project {config.project_id}, {len(scenarios)} scenario(s)")
    for s in scenarios:
        typer.echo(
            f"  {s.scenario_id} v{s.version} [{s.agent_id}] {s.dataset.value} {s.criticality.value}"
        )


@app.command()
def run(
    project_dir: Path = typer.Argument(..., exists=True, help="Directory with evalkit.yaml."),
    agent: str = typer.Option(..., "--agent", "-a", help="Agent id from evalkit.yaml."),
    profile: Profile = typer.Option(Profile.STANDARD, "--profile", "-p", case_sensitive=False),
    data_dir: Path | None = typer.Option(
        None, "--data-dir", help="Defaults to $EVALKIT_DATA_DIR or ./data."
    ),
    seed: int | None = typer.Option(None, help="Campaign seed (stochastic adapters)."),
    repetitions: int | None = typer.Option(None, help="Override repetitions for every scenario."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; no agent call."),
    stop_on_eliminatory: bool = typer.Option(False, help="Stop the campaign on a blocking FAIL."),
    report: bool = typer.Option(True, help="Write JSON + Markdown report after the run."),
    workers: int = typer.Option(1, "--workers", "-w", min=1, help="Concurrent scenarios."),
    baseline: str | None = typer.Option(None, help="Baseline campaign id for paired comparison."),
) -> None:
    """Plan and execute an evaluation campaign; persist runs, results, audit events, report."""
    from evalkit.core import CampaignRefusedError, CampaignRunner, ScenarioLoadError
    from evalkit.reporting import write_report

    repo = _repo(data_dir)
    runner = CampaignRunner(
        repo, actor="cli", stop_on_eliminatory=stop_on_eliminatory, max_workers=workers
    )
    try:
        planned = runner.plan(
            project_dir,
            agent,
            profile=profile,
            seed=seed,
            repetitions_override=repetitions,
            dry_run=dry_run,
            baseline_campaign_id=baseline,
        )
    except (CampaignRefusedError, ScenarioLoadError, KeyError) as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"campaign {planned.campaign.campaign_id} — profile {profile.value}")
    typer.echo(
        f"  agent {agent} v{planned.adapter.agent_version}"
        f" via {planned.adapter.capabilities.adapter_id}"
    )
    typer.echo(f"  scenarios: {len(planned.scenarios)}, planned runs: {planned.planned_runs}")
    for rule in planned.rules:
        typer.echo(f"  rule: {rule}")
    assert planned.campaign.plan is not None
    plan = planned.campaign.plan
    typer.echo(
        f"  forecast: tokens={plan.expected_tokens} agent_cost={plan.expected_agent_cost}"
        f" basis={plan.basis} — {plan.uncertainty}"
    )
    if planned.price:
        typer.echo(
            f"  price snapshot: {planned.price.price_id}"
            f" (verified {planned.price.verified_at:%Y-%m-%d})"
        )
    campaign = asyncio.run(runner.execute(planned))
    typer.echo(
        f"  status: {campaign.status.value}"
        + (f" ({campaign.stop_reason})" if campaign.stop_reason else "")
    )
    if report and not dry_run:
        from evalkit.reporting import export_campaign_csv, write_campaign_html
        from evalkit.scoring import build_scorecard

        card = build_scorecard(
            repo,
            campaign.campaign_id,
            weights=planned.config.weights or None,
        )
        typer.echo(f"  scorecard: {card.overall_status.value} ({card.scorecard_id})")
        for w in card.validity_warnings:
            typer.echo(f"    warning: {w}")
        out = _data_dir(data_dir) / "reports"
        json_path, md_path = write_report(repo, campaign.campaign_id, out)
        html_path = write_campaign_html(repo, campaign.campaign_id, out)
        export_campaign_csv(repo, campaign.campaign_id, out)
        typer.echo(f"  report: {html_path} / {md_path} / {json_path} (+ CSV)")


@app.command("report")
def report_cmd(
    campaign_id: str = typer.Argument(...),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
    out: Path | None = typer.Option(None, help="Output directory (default <data>/reports)."),
) -> None:
    """(Re)generate the JSON + Markdown report of a stored campaign."""
    from evalkit.reporting import export_campaign_csv, write_campaign_html, write_report

    repo = _repo(data_dir)
    target = out or _data_dir(data_dir) / "reports"
    json_path, md_path = write_report(repo, campaign_id, target)
    html_path = write_campaign_html(repo, campaign_id, target)
    csvs = export_campaign_csv(repo, campaign_id, target)
    typer.echo("\n".join(str(p) for p in (html_path, md_path, json_path, *csvs)))


@app.command("campaigns")
def campaigns_cmd(
    project: str = typer.Option(..., "--project"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """List stored campaigns of a project."""
    repo = _repo(data_dir)
    for c in repo.list_campaigns(project):
        typer.echo(
            f"{c.campaign_id}  {c.created_at:%Y-%m-%d %H:%M}  {c.agent_id} v{c.agent_version}"
            f"  {c.profile.value}  {c.status.value}"
        )


@db_app.command("migrate")
def db_migrate(data_dir: Path | None = typer.Option(None, "--data-dir")) -> None:
    """Apply pending schema migrations."""
    from evalkit.storage import SQLiteRepository

    repo = SQLiteRepository(_data_dir(data_dir))
    applied = repo.migrate()
    typer.echo(f"applied: {applied or 'none'}; current: {repo.applied_migrations()}")


@db_app.command("check")
def db_check(data_dir: Path | None = typer.Option(None, "--data-dir")) -> None:
    """Verify the audit hash chain and SQLite integrity."""
    repo = _repo(data_dir)
    ok, n = repo.verify_chain()
    integrity = repo._conn.execute("PRAGMA integrity_check").fetchone()[0]
    typer.echo(
        f"audit chain: {'OK' if ok else 'BROKEN at sequence ' + str(n)} ({n} events);"
        f" sqlite: {integrity}"
    )
    if not ok or integrity != "ok":
        raise typer.Exit(code=1)


@db_app.command("export-audit")
def db_export_audit(
    out: Path = typer.Argument(...),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
    campaign: str | None = typer.Option(None),
) -> None:
    """Export audit events as JSONL."""
    repo = _repo(data_dir)
    n = repo.export_jsonl(str(out), **({"campaign_id": campaign} if campaign else {}))
    typer.echo(f"{n} events -> {out}")


@app.command("compare")
def compare_cmd(
    baseline: str = typer.Argument(...),
    candidate: str = typer.Argument(...),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
    margin: float = typer.Option(0.0, help="Regression margin on the valid-run rate."),
) -> None:
    """Paired comparison (by scenario) of two stored campaigns' valid-run rates."""
    from evalkit.reporting.basic import _equivalence, _scenario_validity
    from evalkit.stats import paired_comparison

    repo = _repo(data_dir)
    cand = repo.get_campaign(candidate)
    base_rates, cand_rates = _scenario_validity(repo, baseline), _scenario_validity(repo, candidate)
    common = sorted(set(base_rates) & set(cand_rates))
    if not common:
        typer.echo("INCONCLUSIVE: no common scenario", err=True)
        raise typer.Exit(code=3)
    res = paired_comparison(
        "valid_run_rate",
        [base_rates[k] for k in common],
        [cand_rates[k] for k in common],
        margin=margin,
    )
    for w in _equivalence(repo, cand.model_copy(update={"baseline_campaign_id": baseline})):
        typer.echo(f"WARNING non-equivalence: {w}")
    typer.echo(
        f"{res.conclusion.value}: {res.baseline_estimate:.3f} -> {res.candidate_estimate:.3f}"
        f" (diff {res.difference:+.3f}); {res.rationale}"
    )
    if res.ci:
        typer.echo(f"  CI {res.ci.level:.0%} [{res.ci.low:.3f}, {res.ci.high:.3f}] {res.ci.method}")
    typer.echo(f"  effect size ({res.effect_size_method}): {res.effect_size}; p={res.p_value}")


@budget_app.command("set")
def budget_set(
    scope: str = typer.Argument(
        ..., help="organization|project|agent|campaign|day|month|evaluation_type"
    ),
    scope_ref: str = typer.Argument(..., help="e.g. demo, demo/greeter, 2026-10-14, *"),
    max_cost: float | None = typer.Option(None),
    max_tokens: int | None = typer.Option(None),
    currency: str = typer.Option("USD"),
    info: float = typer.Option(0.5),
    warning: float = typer.Option(0.8),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Create or replace a budget (a governance action, audited)."""
    from evalkit.contracts import Budget, BudgetScope, BudgetThresholds
    from evalkit.cost_controller import SQLiteCostController

    repo = _repo(data_dir)
    budget = Budget(
        budget_id=f"bud_{scope}_{scope_ref}".replace("/", "_"),
        scope=BudgetScope(scope),
        scope_ref=scope_ref,
        max_cost=max_cost,
        max_tokens=max_tokens,
        currency=currency,
        thresholds=BudgetThresholds(info=info, warning=warning),
    )
    SQLiteCostController(repo, actor="cli").save_budget(budget)
    typer.echo(f"budget {budget.budget_id} saved")


@budget_app.command("status")
def budget_status(
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Show budgets with spent (settled + open reservations)."""
    from evalkit.contracts import Budget
    from evalkit.cost_controller import SQLiteCostController

    repo = _repo(data_dir)
    ctl = SQLiteCostController(repo)
    for row in repo._conn.execute("SELECT json FROM budgets ORDER BY scope, scope_ref"):
        b = Budget.model_validate_json(row["json"])
        cost, tokens = ctl.spent(b.budget_id)
        typer.echo(
            f"{b.budget_id}: {b.scope.value}/{b.scope_ref} spent {cost:.6f}/{b.max_cost}"
            f" {b.currency},"
            f" tokens {tokens}/{b.max_tokens}"
        )


@prices_app.command("import")
def prices_import(
    path: Path = typer.Argument(..., exists=True),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Import PriceEntry records from a YAML file (see prices/TEMPLATE.prices.yaml)."""
    from evalkit.cost_controller import import_prices

    repo = _repo(data_dir)
    for e in import_prices(repo, path):
        typer.echo(f"{e.price_id}: {e.provider}/{e.model_id} from {e.valid_from} ({e.source})")


@prices_app.command("list")
def prices_list(data_dir: Path | None = typer.Option(None, "--data-dir")) -> None:
    """List price registry entries."""
    from evalkit.contracts import PriceEntry

    repo = _repo(data_dir)
    for row in repo._conn.execute(
        "SELECT json FROM prices ORDER BY provider, model_id, valid_from"
    ):
        e = PriceEntry.model_validate_json(row["json"])
        typer.echo(
            f"{e.price_id}: in={e.input_per_million} out={e.output_per_million} {e.currency}"
            f" valid {e.valid_from}..{e.valid_to or 'now'} verified {e.verified_at:%Y-%m-%d}"
        )


@app.command("scorecard")
def scorecard_cmd(
    campaign_id: str = typer.Argument(...),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
    project_dir: Path | None = typer.Option(None, help="Project dir to read weights from."),
) -> None:
    """Build (and persist) the scorecard of a stored campaign."""
    from evalkit.core import load_project
    from evalkit.scoring import build_scorecard

    repo = _repo(data_dir)
    weights = load_project(project_dir).weights if project_dir else None
    card = build_scorecard(repo, campaign_id, weights=weights or None)
    typer.echo(f"{card.scorecard_id}: {card.overall_status.value}")
    for d in card.dimensions:
        rate = "n/a" if d.pass_rate is None else f"{d.pass_rate:.0%}"
        ci = f"[{d.ci.low:.2f}, {d.ci.high:.2f}]" if d.ci else ""
        typer.echo(f"  {d.dimension.value:22} {d.status.value:14} {rate:>5} {ci} n={d.n_evaluated}")
    if card.eliminatory_failures:
        typer.echo(f"  eliminatory: {card.eliminatory_failures}")
    if card.aggregate_score is not None:
        typer.echo(f"  aggregate: {card.aggregate_score:.3f} — {card.aggregate_formula}")
    for r in card.regressions:
        typer.echo(f"  regression: {r}")
    for w in card.validity_warnings:
        typer.echo(f"  warning: {w}")


dashboard_app = typer.Typer(no_args_is_help=True, help="Static HTML dashboard.")
app.add_typer(dashboard_app, name="dashboard")


@dashboard_app.command("build")
def dashboard_build(
    project: str = typer.Option(..., "--project"),
    out: Path | None = typer.Option(None, help="Output dir (default <data>/dashboard/<project>)."),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Generate index, agent, campaign, finances and improvement pages from stored data."""
    from evalkit.reporting import build_dashboard

    repo = _repo(data_dir)
    target = out or _data_dir(data_dir) / "dashboard" / project
    for path in build_dashboard(repo, project, target):
        typer.echo(str(path))


api_app = typer.Typer(no_args_is_help=True, help="HTTP API server.")
app.add_typer(api_app, name="api")


@api_app.command("serve")
def api_serve(
    host: str = typer.Option("127.0.0.1", help="Bind address (loopback by default)."),
    port: int = typer.Option(8765),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
    projects_dir: Path | None = typer.Option(None, help="Root holding <project_id>/evalkit.yaml."),
) -> None:
    """Serve the /v1 API (requires EVALKIT_API_KEY in the environment)."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        typer.echo("install the api extra: pip install 'graines-evalkit[api]'", err=True)
        raise typer.Exit(code=1) from exc
    if data_dir:
        os.environ["EVALKIT_DATA_DIR"] = str(data_dir)
    if projects_dir:
        os.environ["EVALKIT_PROJECTS_DIR"] = str(projects_dir)
    if not os.environ.get("EVALKIT_API_KEY"):
        typer.echo("EVALKIT_API_KEY is not set: every protected endpoint will answer 503", err=True)
    uvicorn.run("evalkit.api.app:app", host=host, port=port, log_level="info")


if __name__ == "__main__":  # pragma: no cover
    app()
