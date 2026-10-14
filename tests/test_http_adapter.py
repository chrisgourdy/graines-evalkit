"""http.json adapter against an in-process httpx MockTransport (no network)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from evalkit.adapters import create_adapter
from evalkit.contracts import Dimension, Provenance, Scenario, UsageSource, VerificationSpec

SCN = Scenario(
    scenario_id="tst.http.001",
    version="1.0.0",
    project_id="tst",
    agent_id="agt",
    name="n",
    description="d",
    objective="o",
    inputs={"q": "hi"},
    expected_behavior="e",
    reference_outputs={"text": "hi"},
    verifications=[VerificationSpec(evaluator="exact_match", dimension=Dimension.ACCURACY)],
    provenance=Provenance(author="t", created_at=datetime(2026, 1, 1, tzinfo=UTC), origin="test"),
)


def _adapter(handler):  # type: ignore[no-untyped-def]
    return create_adapter(
        "http.json",
        "2",
        {
            "url": "http://agent.local/run",
            "transport": httpx.MockTransport(handler),
            "headers": {"X-Key": "k"},
        },
    )


def test_http_adapter_happy_path_with_usage_and_steps() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["key"] = request.headers.get("X-Key")
        return httpx.Response(
            200,
            json={
                "output": {"text": "hi"},
                "usage": [
                    {
                        "provider": "openai",
                        "model": "gpt-x",
                        "source": "REPORTED",
                        "input_tokens": 5,
                        "output_tokens": 2,
                    }
                ],
                "steps": [
                    {
                        "index": 0,
                        "kind": "terminal",
                        "state": "s",
                        "action": "done",
                        "started_at": "2026-01-01T00:00:00Z",
                    }
                ],
                "agent_version": "2.1",
            },
        )

    r = asyncio.run(_adapter(handler).invoke(SCN, seed=7, timeout_s=5))
    assert r.output == {"text": "hi"} and r.agent_version == "2.1"
    assert r.usage[0].source is UsageSource.REPORTED and len(r.trajectory_steps) == 1
    assert seen["body"] == {
        "scenario_id": "tst.http.001",
        "inputs": {"q": "hi"},
        "context": {},
        "seed": 7,
    }
    assert seen["key"] == "k"


def test_http_adapter_errors_are_returned_not_raised() -> None:
    def bad_status(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    r = asyncio.run(_adapter(bad_status).invoke(SCN, seed=None, timeout_s=5))
    assert r.output is None and "500" in str(r.metadata["error"])
    assert r.usage[0].source is UsageSource.UNKNOWN

    def not_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>")

    assert "non-JSON" in str(
        asyncio.run(_adapter(not_json).invoke(SCN, seed=None, timeout_s=5)).metadata["error"]
    )

    def raises(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    assert "http error" in str(
        asyncio.run(_adapter(raises).invoke(SCN, seed=None, timeout_s=5)).metadata["error"]
    )

    def agent_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output": None, "error": "agent failed"})

    assert (
        asyncio.run(_adapter(agent_error).invoke(SCN, seed=None, timeout_s=5)).metadata["error"]
        == "agent failed"
    )


def test_http_adapter_validates_url() -> None:
    with pytest.raises(ValueError, match=r"params\.url"):
        create_adapter("http.json", "1", {"url": "ftp://x"})
