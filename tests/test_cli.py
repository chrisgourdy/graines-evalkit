from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from evalkit import __version__
from evalkit.cli.main import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
    assert "contracts" in result.stdout


def test_export_schemas(tmp_path: Path) -> None:
    result = runner.invoke(app, ["export-schemas", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "Run.schema.json").is_file()
