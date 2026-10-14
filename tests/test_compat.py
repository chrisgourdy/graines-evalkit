"""Compatibility: the same campaign through CLI, HTTP API and the TypeScript SDK yields the
same persisted shape of results. Runs a real uvicorn server on a random loopback port; the SDK
part needs node + a built SDK (skipped otherwise, never silently passed)."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "sdk" / "typescript"
KEY = "compat-key"

pytestmark = pytest.mark.integration_local


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def server(
    tmp_path: Path, demo_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[str, Path]]:
    projects = tmp_path / "projects"
    shutil.copytree(demo_dir, projects / "demo")
    data = tmp_path / "data"
    monkeypatch.setenv("EVALKIT_DATA_DIR", str(data))
    monkeypatch.setenv("EVALKIT_PROJECTS_DIR", str(projects))
    monkeypatch.setenv("EVALKIT_API_KEY", KEY)
    from evalkit.api.app import create_app

    port = _free_port()
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{base}/v1/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        raise AssertionError("server did not start")
    yield base, data
    srv.should_exit = True
    thread.join(timeout=5)


def _wait(base: str, cid: str) -> dict:  # type: ignore[type-arg]
    for _ in range(300):
        c = httpx.get(
            f"{base}/v1/campaigns/{cid}", headers={"X-EvalKit-Key": KEY}, timeout=5
        ).json()
        if c["status"] not in ("PLANNED", "RUNNING"):
            return c
        time.sleep(0.1)
    raise AssertionError("timeout")


def _shape(report: dict) -> dict:  # type: ignore[type-arg]
    """The comparable part of a report: statuses and counts, not ids/timestamps."""
    return {
        "overall": report["overall_status"],
        "runs": report["runs"],
        "valid": report["valid_runs"],
        "dims": {k: (v["n"], v["pass"], v["fail"]) for k, v in report["dimensions"].items()},
        "usage_status": report["usage"]["status"],
        "tokens": report["usage"]["tokens"],
    }


def test_cli_api_sdk_produce_the_same_results(server: tuple[str, Path], demo_dir: Path) -> None:
    base, data = server
    h = {"X-EvalKit-Key": KEY}
    # 1) CLI (same data dir, deterministic agent → identical outputs)
    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "evalkit.cli.main",
            "run",
            str(demo_dir),
            "--agent",
            "greeter",
            "-p",
            "standard",
            "--data-dir",
            str(data),
            "--no-report",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    cli_cid = cli.stdout.split()[1]
    cli_report = httpx.get(f"{base}/v1/campaigns/{cli_cid}/report", headers=h, timeout=10).json()
    # 2) API
    api_cid = httpx.post(
        f"{base}/v1/campaigns",
        json={"project_id": "demo", "agent_id": "greeter", "profile": "STANDARD"},
        headers=h,
        timeout=10,
    ).json()["campaign_id"]
    assert _wait(base, api_cid)["status"] == "COMPLETED"
    api_report = httpx.get(f"{base}/v1/campaigns/{api_cid}/report", headers=h, timeout=10).json()
    assert _shape(cli_report) == _shape(api_report)
    # 3) SDK (node) — skipped explicitly when unavailable
    node = shutil.which("node")
    if node is None or not (SDK / "dist" / "index.js").is_file():
        pytest.skip("node or built SDK unavailable: SDK leg of the compatibility test not run")
    script = f"""
    import {{ EvalkitClient }} from "{(SDK / "dist" / "index.js").as_posix()}";
    const c = new EvalkitClient({{ baseUrl: "{base}", apiKey: "{KEY}" }});
    const req = {{ project_id: "demo", agent_id: "greeter", profile: "STANDARD" }};
    const launched = await c.launchCampaign(req);
    const done = await c.waitForCampaign(launched.campaign_id, {{ intervalMs: 100 }});
    const report = await c.getReport(done.campaign_id);
    const card = await c.getScorecard(done.campaign_id);
    const usage = {{ provider: "sim", model: "sim-deterministic-1", source: "REPORTED",
      input_tokens: 3, output_tokens: 2 }};
    const pushed = await c.pushUsage({{ project_id: "demo", agent_id: "js", usage }});
    const card_status = card.overall_status;
    console.log(JSON.stringify({{ status: done.status, report, card_status, pushed }}));
    """
    out = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    sdk = json.loads(out.stdout.strip().splitlines()[-1])
    assert sdk["status"] == "COMPLETED" and sdk["card_status"] == "PASS"
    assert _shape(sdk["report"]) == _shape(cli_report)
    assert sdk["pushed"]["usage_id"].startswith("usg_")
