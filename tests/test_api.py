"""HTTP API /v1 — auth, campaign launch/poll, results, scorecard, usage and event push."""

from __future__ import annotations

import shutil
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evalkit.api.app import create_app

KEY = "test-key-123"


@pytest.fixture
def api(tmp_path: Path, demo_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    projects = tmp_path / "projects"
    shutil.copytree(demo_dir, projects / "demo")
    monkeypatch.setenv("EVALKIT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EVALKIT_PROJECTS_DIR", str(projects))
    monkeypatch.setenv("EVALKIT_API_KEY", KEY)
    with TestClient(create_app()) as client:
        yield client


def _wait(api: TestClient, cid: str, timeout: float = 30.0) -> dict:  # type: ignore[type-arg]
    deadline = time.time() + timeout
    while time.time() < deadline:
        c = api.get(f"/v1/campaigns/{cid}", headers={"X-EvalKit-Key": KEY}).json()
        if c["status"] not in ("PLANNED", "RUNNING"):
            return c
        time.sleep(0.1)
    raise AssertionError("campaign did not finish")


def test_health_is_open_and_everything_else_needs_a_key(api: TestClient) -> None:
    assert api.get("/v1/health").json()["status"] == "ok"
    assert api.get("/v1/projects/demo/campaigns").status_code == 401
    assert (
        api.get("/v1/projects/demo/campaigns", headers={"X-EvalKit-Key": "nope"}).status_code == 401
    )
    assert api.get("/v1/projects/demo/campaigns", headers={"X-EvalKit-Key": KEY}).status_code == 200


def test_api_refuses_to_run_without_configured_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EVALKIT_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.delenv("EVALKIT_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        assert client.get("/v1/health").status_code == 200
        r = client.get("/v1/projects/demo/campaigns", headers={"X-EvalKit-Key": "x"})
        assert r.status_code == 503


def test_launch_poll_results_scorecard_report_events(api: TestClient) -> None:
    h = {"X-EvalKit-Key": KEY}
    r = api.post(
        "/v1/campaigns",
        json={"project_id": "demo", "agent_id": "greeter", "profile": "STANDARD"},
        headers=h,
    )
    assert r.status_code == 202, r.text
    cid = r.json()["campaign_id"]
    assert api.get(f"/v1/campaigns/{cid}/scorecard", headers=h).status_code in (409, 200)
    final = _wait(api, cid)
    assert final["status"] == "COMPLETED"
    runs = api.get(f"/v1/campaigns/{cid}/runs", headers=h).json()
    assert len(runs) == 2 and all(r["status"] == "COMPLETED" for r in runs)
    results = api.get(f"/v1/campaigns/{cid}/results", headers=h).json()
    assert results and {x["status"] for x in results} == {"PASS"}
    card = api.get(f"/v1/campaigns/{cid}/scorecard", headers=h).json()
    assert card["overall_status"] == "PASS" and card["campaign_id"] == cid
    report = api.get(f"/v1/campaigns/{cid}/report", headers=h).json()
    assert report["overall_status"] == "PASS" and report["runs"] == 2
    events = api.get(f"/v1/campaigns/{cid}/events", headers=h).json()
    assert events[0]["event_type"] == "campaign.started"
    assert any(
        c["campaign_id"] == cid for c in api.get("/v1/projects/demo/campaigns", headers=h).json()
    )


def test_launch_errors(api: TestClient) -> None:
    h = {"X-EvalKit-Key": KEY}
    assert (
        api.post(
            "/v1/campaigns", json={"project_id": "nope", "agent_id": "a"}, headers=h
        ).status_code
        == 404
    )
    assert (
        api.post(
            "/v1/campaigns", json={"project_id": "demo", "agent_id": "nope"}, headers=h
        ).status_code
        == 422
    )
    assert api.get("/v1/campaigns/cmp_missing", headers=h).status_code == 404


def test_push_usage_and_events(api: TestClient) -> None:
    h = {"X-EvalKit-Key": KEY}
    r = api.post(
        "/v1/usage",
        json={
            "project_id": "demo",
            "agent_id": "js-agent",
            "usage": {
                "provider": "openai",
                "model": "gpt-x",
                "source": "REPORTED",
                "input_tokens": 10,
                "output_tokens": 5,
            },
        },
        headers=h,
    )
    assert r.status_code == 201 and r.json()["cost_status"] == "UNKNOWN"  # no tariff for gpt-x
    e = api.post(
        "/v1/events",
        json={"event_type": "tool.called", "project_id": "demo", "payload": {"tool": "x"}},
        headers=h,
    )
    assert e.status_code == 201 and e.json()["sequence"] >= 1
    forbidden = api.post("/v1/events", json={"event_type": "permission.changed"}, headers=h)
    assert forbidden.status_code == 403
    assert api.post("/v1/events", json={"event_type": "not.a.type"}, headers=h).status_code == 422
    assert "Scenario" in api.get("/v1/schemas", headers=h).json()
