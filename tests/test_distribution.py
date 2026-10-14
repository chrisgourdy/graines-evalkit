"""Acceptance scenario 22: the wheel installs in a clean venv and runs the demo."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration_local
def test_wheel_installs_in_clean_venv(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not available")
    dist = tmp_path / "dist"
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(dist)], cwd=ROOT, check=True, timeout=600
    )
    wheels = list(dist.glob("graines_evalkit-*.whl"))
    assert len(wheels) == 1, wheels
    venv = tmp_path / "clean"
    subprocess.run([uv, "venv", str(venv), "--python", sys.executable], check=True, timeout=120)
    py = venv / "bin" / "python"
    subprocess.run(
        [uv, "pip", "install", "--python", str(py), str(wheels[0])], check=True, timeout=600
    )
    exe = venv / "bin" / "evalkit"
    out = subprocess.run(
        [str(exe), "version"], capture_output=True, text=True, check=True, timeout=60
    )
    assert out.stdout.startswith("evalkit ")
    run = subprocess.run(
        [
            str(exe),
            "run",
            str(ROOT / "scenarios" / "examples" / "demo"),
            "--agent",
            "greeter",
            "-p",
            "quick",
            "--data-dir",
            str(tmp_path / "data"),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert run.returncode == 0 and "status: COMPLETED" in run.stdout, run.stdout + run.stderr
    assert "scorecard: PASS" in run.stdout
