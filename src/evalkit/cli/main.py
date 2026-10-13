"""``evalkit`` command-line interface."""

from __future__ import annotations

import typer

from evalkit import __version__

app = typer.Typer(no_args_is_help=True, help="EVALKIT — evaluate, meter and improve AI agents.")


@app.command()
def version() -> None:
    """Print EVALKIT version and contract schema version."""
    from evalkit.contracts import CONTRACT_SCHEMA_VERSION

    typer.echo(f"evalkit {__version__} (contracts {CONTRACT_SCHEMA_VERSION})")


@app.command("export-schemas")
def export_schemas(out: str = typer.Option("schemas", help="Output directory.")) -> None:
    """Export JSON Schemas of public contracts (source of the TypeScript SDK types)."""
    from pathlib import Path

    from evalkit.contracts import export_json_schemas

    for path in export_json_schemas(Path(out)):
        typer.echo(str(path))
