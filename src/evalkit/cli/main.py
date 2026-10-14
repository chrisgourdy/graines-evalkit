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
app.add_typer(db_app, name="db")
app.add_typer(scenarios_app, name="scenarios")


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
) -> None:
    """Plan and execute an evaluation campaign; persist runs, results, audit events, report."""
    from evalkit.core import CampaignRefusedError, CampaignRunner, ScenarioLoadError
    from evalkit.reporting import write_report

    repo = _repo(data_dir)
    runner = CampaignRunner(repo, actor="cli", stop_on_eliminatory=stop_on_eliminatory)
    try:
        planned = runner.plan(
            project_dir,
            agent,
            profile=profile,
            seed=seed,
            repetitions_override=repetitions,
            dry_run=dry_run,
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
    typer.echo(f"  forecast: {planned.campaign.plan.uncertainty}")
    campaign = asyncio.run(runner.execute(planned))
    typer.echo(
        f"  status: {campaign.status.value}"
        + (f" ({campaign.stop_reason})" if campaign.stop_reason else "")
    )
    if report and not dry_run:
        json_path, md_path = write_report(
            repo, campaign.campaign_id, _data_dir(data_dir) / "reports"
        )
        typer.echo(f"  report: {md_path} / {json_path}")


@app.command("report")
def report_cmd(
    campaign_id: str = typer.Argument(...),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
    out: Path | None = typer.Option(None, help="Output directory (default <data>/reports)."),
) -> None:
    """(Re)generate the JSON + Markdown report of a stored campaign."""
    from evalkit.reporting import write_report

    repo = _repo(data_dir)
    json_path, md_path = write_report(repo, campaign_id, out or _data_dir(data_dir) / "reports")
    typer.echo(f"{md_path}\n{json_path}")


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
