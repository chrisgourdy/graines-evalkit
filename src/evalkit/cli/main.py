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


# --- Phase 6: tickets, retrofit, learnings, self-check -------------------------------------

tickets_app = typer.Typer(no_args_is_help=True, help="Backlog tickets (FEEDBACK).")
retrofit_app = typer.Typer(no_args_is_help=True, help="Retrofit cycle (IMPROVEMENT).")
learnings_app = typer.Typer(no_args_is_help=True, help="Knowledge base of learnings.")
backlog_app = typer.Typer(no_args_is_help=True, help="Backlog export.")
app.add_typer(tickets_app, name="tickets")
app.add_typer(retrofit_app, name="retrofit")
app.add_typer(learnings_app, name="learnings")
app.add_typer(backlog_app, name="backlog")


@tickets_app.command("detect")
def tickets_detect(
    campaign_id: str = typer.Argument(...),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
    project_dir: Path | None = typer.Option(None, help="Project dir to read weights from."),
) -> None:
    """Build the scorecard of a campaign and open tickets for every incident found."""
    from evalkit.core import load_project
    from evalkit.feedback import TicketStore
    from evalkit.scoring import build_scorecard

    repo = _repo(data_dir)
    weights = load_project(project_dir).weights if project_dir else None
    card = build_scorecard(repo, campaign_id, weights=weights or None)
    opened = TicketStore(repo, actor="cli").detect_incidents(card)
    typer.echo(f"scorecard {card.scorecard_id}: {card.overall_status.value}")
    if not opened:
        typer.echo("no incident detected")
    for t in opened:
        link = f" -> {t.related_tickets[0]}" if t.related_tickets else ""
        typer.echo(f"  {t.ticket_id} {t.status.value:10} P{t.priority} {t.title}{link}")


@tickets_app.command("list")
def tickets_list(
    project: str = typer.Option(..., "--project"),
    status: str | None = typer.Option(None, help="Filter by status."),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """List tickets of a project."""
    repo = _repo(data_dir)
    for t in repo.list_tickets(project):
        if status and t.status.value != status.upper():
            continue
        typer.echo(
            f"{t.ticket_id} {t.status.value:12} P{t.priority} {t.severity.value:8} "
            f"{t.agent_id}@{t.agent_version} {t.title}"
        )


@tickets_app.command("show")
def tickets_show(
    ticket_id: str = typer.Argument(...), data_dir: Path | None = typer.Option(None, "--data-dir")
) -> None:
    """Print a ticket as JSON."""
    repo = _repo(data_dir)
    typer.echo(repo.get_ticket(ticket_id).model_dump_json(indent=2))


@tickets_app.command("transition")
def tickets_transition(
    ticket_id: str = typer.Argument(...),
    status: str = typer.Argument(..., help="Target status (workflow 1.0.0)."),
    note: str = typer.Option(..., "--note", help="Why (recorded in the ticket history)."),
    decision: str | None = typer.Option(None, help="Decision text for VALIDATED/REJECTED/CLOSED."),
    actor: str = typer.Option("human", help="Who decides (recorded in the audit trail)."),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Move a ticket through the workflow (invalid transitions are refused)."""
    from evalkit.contracts import TicketStatus
    from evalkit.feedback import TicketStore

    repo = _repo(data_dir)
    try:
        t = TicketStore(repo, actor=actor).transition(
            ticket_id, TicketStatus(status.upper()), note, decision=decision
        )
    except ValueError as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"{t.ticket_id}: {t.status.value}")


@backlog_app.command("export")
def backlog_export(
    project: str = typer.Option(..., "--project"),
    out: Path | None = typer.Option(None, help="Markdown file (default: stdout)."),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Render the ticket backlog of a project as Markdown (docs/BACKLOG.md format)."""
    from evalkit.feedback import render_backlog_markdown

    md = render_backlog_markdown(_repo(data_dir), project)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        typer.echo(str(out))
    else:
        typer.echo(md)


@retrofit_app.command("run")
def retrofit_run(
    project_dir: Path = typer.Option(..., "--project-dir", exists=True),
    agent: str = typer.Option(..., "--agent"),
    broken: str = typer.Option(..., "--broken", help="Campaign id showing the incident."),
    good: str = typer.Option(..., "--good", help="Last known-good campaign id (baseline)."),
    params: str | None = typer.Option(
        None, help="JSON params patch to test instead of reverting to the good config."
    ),
    version: str | None = typer.Option(None, help="Agent version to test with --params."),
    max_iterations: int = typer.Option(2, "--max-iterations", min=1),
    seed: int = typer.Option(0),
    actor: str = typer.Option("cli"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Run the retrofit cycle OBSERVE→…→LEARN on an isolated copy of the project (no HOLDOUT)."""
    import json

    from evalkit.improvement import RetrofitCycle, params_override

    provider = params_override(json.loads(params), version) if params else None
    cycle = RetrofitCycle(
        _repo(data_dir),
        actor=actor,
        fix_provider=provider,
        max_iterations=max_iterations,
        seed=seed,
    )
    res = cycle.run(project_dir, agent, broken_campaign_id=broken, good_campaign_id=good)
    typer.echo(f"experiment {res.experiment_id}: {res.decision}")
    typer.echo(f"  steps: {' > '.join(res.steps)}")
    typer.echo(f"  ticket: {res.ticket_id or 'n/a'}")
    typer.echo(f"  candidate campaign: {res.candidate_campaign_id or 'n/a'}")
    typer.echo(f"  fix: {json.dumps(res.fix, sort_keys=True) if res.fix else 'n/a'}")
    typer.echo(f"  learning: {res.learning_id or 'n/a'}")
    typer.echo(f"  rationale: {res.rationale}")


@retrofit_app.command("confirm")
def retrofit_confirm(
    project_dir: Path = typer.Option(..., "--project-dir", exists=True),
    agent: str = typer.Option(..., "--agent"),
    good: str = typer.Option(..., "--good", help="Last known-good campaign id (baseline)."),
    learning: str = typer.Option(..., "--learning", help="Learning id to confirm."),
    seed: int = typer.Option(0),
    actor: str = typer.Option("human"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Confirm an observed learning on a DEEP campaign of the real project (HOLDOUT included)."""
    from evalkit.improvement import RetrofitCycle

    res = RetrofitCycle(_repo(data_dir), actor=actor, seed=seed).confirm(
        project_dir, agent, good_campaign_id=good, learning_id=learning
    )
    for k, v in res.items():
        typer.echo(f"  {k}: {v}")


@learnings_app.command("list")
def learnings_list(
    project: str = typer.Option(..., "--project"),
    status: str | None = typer.Option(None),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """List learnings of a project with their validation status."""
    from evalkit.improvement import LearningStore

    for it in LearningStore(_repo(data_dir)).list(project, status):
        typer.echo(f"{it['learning_id']} {it['status']:9} {it['scope']:20} {it['statement']}")


@learnings_app.command("set-status")
def learnings_set_status(
    learning_id: str = typer.Argument(...),
    status: str = typer.Argument(..., help="observed | verified | adopted | rejected"),
    actor: str = typer.Option("human"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Change a learning's status (adoption is a human decision)."""
    from evalkit.improvement import LearningStore

    it = LearningStore(_repo(data_dir), actor=actor).set_status(learning_id, status)
    typer.echo(f"{it['learning_id']}: {it['status']}")


@learnings_app.command("export")
def learnings_export(
    project: str = typer.Option(..., "--project"),
    out: Path | None = typer.Option(None, help="Markdown file (default: stdout)."),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Render the learnings of a project as Markdown (docs/LEARNINGS.md format)."""
    from evalkit.improvement import LearningStore

    md = LearningStore(_repo(data_dir)).render_markdown(project)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        typer.echo(str(out))
    else:
        typer.echo(md)


@app.command("self-check")
def self_check(
    data_dir: Path | None = typer.Option(None, "--data-dir"),
    no_persist: bool = typer.Option(False, "--no-persist", help="Do not store the scorecard."),
) -> None:
    """Evaluate EVALKIT's own mechanisms (statistics, metering, cost, budgets, audit, schemas)."""
    from evalkit.improvement import self_evaluate

    card, details = self_evaluate(_repo(data_dir), persist=not no_persist)
    for name, ok, msg in details:
        mark = "PASS" if ok else "FAIL" if ok is False else "NOT_EVALUATED"
        typer.echo(f"  {name:18} {mark:14} {msg}")
    typer.echo(f"{card.scorecard_id}: {card.overall_status.value}")
    if card.overall_status.value == "FAIL":
        raise typer.Exit(code=1)


# --- Phase 7: resume, backup/restore, apply/rollback, scheduler --------------------------

campaign_app = typer.Typer(no_args_is_help=True, help="Campaign lifecycle (resume).")
schedule_app = typer.Typer(no_args_is_help=True, help="Unattended execution from a YAML plan.")
app.add_typer(campaign_app, name="campaign")
app.add_typer(schedule_app, name="schedule")


@campaign_app.command("resume")
def campaign_resume(
    campaign_id: str = typer.Argument(...),
    project_dir: Path = typer.Option(..., "--project-dir", exists=True),
    workers: int = typer.Option(1, "--workers", "-w", min=1),
    actor: str = typer.Option("human"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Resume an interrupted (RUNNING/FAILED) campaign from persisted state."""
    from evalkit.core import CampaignRefusedError, CampaignRunner
    from evalkit.reporting import export_campaign_csv, write_campaign_html, write_report
    from evalkit.scoring import build_scorecard

    repo = _repo(data_dir)
    runner = CampaignRunner(repo, actor=actor, max_workers=workers)
    try:
        planned = runner.resume(project_dir, campaign_id)
    except CampaignRefusedError as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for rule in planned.rules:
        typer.echo(f"  rule: {rule}")
    campaign = asyncio.run(runner.execute(planned))
    typer.echo(f"  status: {campaign.status.value}")
    card = build_scorecard(repo, campaign.campaign_id, weights=planned.config.weights or None)
    typer.echo(f"  scorecard: {card.overall_status.value} ({card.scorecard_id})")
    out = _data_dir(data_dir) / "reports"
    write_report(repo, campaign.campaign_id, out)
    write_campaign_html(repo, campaign.campaign_id, out)
    export_campaign_csv(repo, campaign.campaign_id, out)


@db_app.command("backup")
def db_backup(
    dest: Path = typer.Argument(..., help="Destination directory (created)."),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
    no_artifacts: bool = typer.Option(False, "--no-artifacts", help="Database only."),
) -> None:
    """Consistent online backup: database (sqlite backup API), artifacts and reports."""
    import json

    manifest = _repo(data_dir).backup(dest, with_artifacts=not no_artifacts)
    typer.echo(json.dumps(manifest, indent=2))
    if not manifest["audit_chain_ok"]:
        typer.echo("WARNING: audit chain of the source is broken", err=True)
        raise typer.Exit(code=1)


@db_app.command("restore")
def db_restore(
    backup_dir: Path = typer.Argument(..., exists=True),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
    yes: bool = typer.Option(False, "--yes", help="Confirm replacing the current data dir."),
) -> None:
    """Replace the data directory with a backup (refused if the backup is corrupt)."""
    from evalkit.storage import SQLiteRepository

    if not yes:
        typer.echo("refusing without --yes: restore replaces the current database", err=True)
        raise typer.Exit(code=2)
    try:
        repo = SQLiteRepository.restore(backup_dir, _data_dir(data_dir))
    except (FileNotFoundError, RuntimeError) as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    repo.migrate()
    ok, n = repo.verify_chain()
    typer.echo(
        f"restored into {_data_dir(data_dir)}: audit chain {'OK' if ok else 'BROKEN'} ({n} events)"
    )


@retrofit_app.command("apply")
def retrofit_apply(
    experiment: str = typer.Argument(..., help="Experiment id with decision APPLY_ALLOWED."),
    project_dir: Path = typer.Option(..., "--project-dir", exists=True),
    actor: str = typer.Option("human"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Apply a validated low-risk fix to the project (policy level 3; backup kept)."""
    from evalkit.improvement import ApplyRefusedError, apply_fix

    try:
        done = apply_fix(_repo(data_dir), project_dir, experiment, actor=actor)
    except ApplyRefusedError as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"applied to agent {done.agent_id}; backup {done.backup_path}")
    typer.echo(f"  before: {done.before}")
    typer.echo(f"  after:  {done.after}")


@retrofit_app.command("rollback")
def retrofit_rollback(
    project_dir: Path = typer.Option(..., "--project-dir", exists=True),
    backup: Path | None = typer.Option(None, help="Specific backup file (default: latest)."),
    reason: str = typer.Option("manual rollback"),
    actor: str = typer.Option("human"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Restore evalkit.yaml from the latest (or given) backup."""
    from evalkit.improvement import ApplyRefusedError, rollback

    try:
        restored = rollback(_repo(data_dir), project_dir, actor=actor, backup=backup, reason=reason)
    except ApplyRefusedError as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"restored from {restored}")


@schedule_app.command("run")
def schedule_run(
    plan: Path = typer.Argument(..., exists=True, help="YAML plan (docs/RUNBOOK.md)."),
    once: bool = typer.Option(False, "--once", help="One tick then exit (cron/systemd)."),
    poll_seconds: float = typer.Option(60.0, min=1.0),
    max_ticks: int | None = typer.Option(None, help="Stop after N ticks (tests)."),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Run due jobs of a plan: campaign → scorecard → optional retrofit/apply/confirm."""
    from evalkit.scheduler import (
        PlanLoadError,
        Scheduler,
        SchedulerLock,
        SchedulerLockedError,
        load_plan,
    )

    try:
        loaded = load_plan(plan)
    except PlanLoadError as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    repo = _repo(data_dir)
    try:
        with SchedulerLock(_data_dir(data_dir)):
            sched = Scheduler(repo, loaded)
            if once:
                for o in sched.tick():
                    typer.echo(_fmt_outcome(o))
            else:
                sched.run_forever(poll_seconds=poll_seconds, max_ticks=max_ticks)
    except SchedulerLockedError as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(code=3) from exc


def _fmt_outcome(o: object) -> str:
    from evalkit.scheduler import JobOutcome

    assert isinstance(o, JobOutcome)
    parts = [f"{o.job:20} {o.action:16}"]
    if o.campaign_id:
        parts.append(o.campaign_id)
    if o.scorecard_status:
        parts.append(f"scorecard={o.scorecard_status}")
    if o.retrofit_decision:
        parts.append(f"retrofit={o.retrofit_decision}")
    if o.applied:
        parts.append("applied")
    if o.confirmed:
        parts.append(f"confirmed={o.confirmed}")
    if o.note:
        parts.append(f"— {o.note}")
    return " ".join(parts)


@schedule_app.command("status")
def schedule_status(
    plan: Path = typer.Argument(..., exists=True),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Show the persisted state of every job of a plan."""
    from evalkit.scheduler import PlanLoadError, Scheduler, load_plan

    try:
        sched = Scheduler(_repo(data_dir), load_plan(plan))
    except PlanLoadError as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for st in sched.states():
        flag = f"PAUSED: {st.paused_reason}" if st.is_paused() else "active"
        typer.echo(
            f"{st.job_name:20} {flag}; last run {st.last_run_at or 'never'};"
            f" last campaign {st.last_campaign_id or 'n/a'};"
            f" running {st.running_campaign_id or '-'};"
            f" last good {st.last_good_campaign_id or 'n/a'}; failures {st.consecutive_failures};"
            f" retrofits today {st.retrofits_today}"
        )


@schedule_app.command("resume-job")
def schedule_resume_job(
    plan: Path = typer.Argument(..., exists=True),
    job: str = typer.Argument(...),
    note: str = typer.Option("", help="Why the human resumes it (audited)."),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Un-pause a job stopped by the failure guard (human decision, audited)."""
    from evalkit.scheduler import Scheduler, load_plan

    st = Scheduler(_repo(data_dir), load_plan(plan)).resume_job(job, note=note)
    typer.echo(f"{st.job_name}: active")


# --- Phase 8: acceptance -------------------------------------------------------------------

acceptance_app = typer.Typer(no_args_is_help=True, help="The 30 acceptance scenarios.")
app.add_typer(acceptance_app, name="acceptance")


@acceptance_app.command("list")
def acceptance_list() -> None:
    """List scenarios, their mode and covering tests (no execution)."""
    from evalkit.acceptance import SCENARIOS, Mode

    for s in SCENARIOS:
        mode = "BLOCKED" if s.mode is Mode.CI else s.mode.value
        typer.echo(f"{s.number:2} {s.title:40} {mode:12} {len(s.tests)} test(s)")
        for t in s.tests:
            typer.echo(f"     {t}")
        if s.blocked_reason:
            typer.echo(f"     blocked: {s.blocked_reason}")


@acceptance_app.command("run")
def acceptance_run(
    out: Path = typer.Option(Path("docs/ACCEPTANCE_REPORT.md"), help="Markdown report path."),
    junit: Path | None = typer.Option(None, help="JUnit XML path (default data/acceptance/)."),
    root: Path = typer.Option(Path(), help="Repository root (contains tests/)."),
    pytest_arg: list[str] = typer.Option([], "--pytest-arg", help="Extra pytest argument."),
) -> None:
    """Execute the whole test suite with JUnit evidence and write the acceptance report."""
    from evalkit.acceptance import run_acceptance

    if not (root / "tests").is_dir():
        typer.echo(
            f"REFUSED: {root} has no tests/ directory (run from a source checkout)", err=True
        )
        raise typer.Exit(code=2)
    report = run_acceptance(root.resolve(), out=out, junit=junit, pytest_args=list(pytest_arg))
    c = report.counts
    typer.echo(
        f"tests: {report.passed} passed, {report.failed} failed, {report.errors} errors, "
        f"{report.skipped} skipped — scenarios: {c['PASS']} PASS, {c['FAIL']} FAIL, "
        f"{c['BLOCKED']} BLOCKED, {c['NOT_RUN']} NOT_RUN"
    )
    for r in report.results:
        if r.result != "PASS":
            typer.echo(f"  {r.scenario.number:2} {r.scenario.title}: {r.result} — {r.detail}")
    typer.echo(f"report: {out}")
    if not report.accepted:
        raise typer.Exit(code=1)
