"""``http.json`` — POST the scenario inputs to any HTTP endpoint (language-agnostic).

Request body: ``{"scenario_id", "inputs", "context", "seed"}``. Expected JSON response:
``{"output": <any>, "usage": [<TokenUsage>...]?, "steps": [<TrajectoryStep>...]?,
"agent_version": str?, "error": str?}``. Missing usage ⇒ UNKNOWN. Requires ``httpx``
(optional dependency ``evalkit[http]``). The response is untrusted data.
"""

from __future__ import annotations

import time
from typing import Any

from evalkit.adapters.interfaces import AdapterCapabilities
from evalkit.contracts import AgentResponse, Scenario, TokenUsage, UsageSource


class HttpJsonAdapter:
    adapter_id = "http.json"
    adapter_version = "1.0.0"

    def __init__(self, agent_version: str, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        url = p.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            msg = "http.json needs params.url (http(s)://...)"
            raise ValueError(msg)
        self.url = url
        self._agent_version = agent_version
        self.headers: dict[str, str] = {
            str(k): str(v) for k, v in dict(p.get("headers", {})).items()
        }
        self.cost_bearing = bool(p.get("cost_bearing", False))
        self.provider = str(p.get("provider", "http"))
        self.model = str(p.get("model", "unknown"))
        self.reports_usage = bool(p.get("reports_usage", False))
        self.transport = p.get("transport")  # test hook (httpx.MockTransport)

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            reports_usage=self.reports_usage,
            reports_trajectory=True,
            deterministic=False,
            supports_seed=True,
            cost_bearing=self.cost_bearing,
        )

    @property
    def agent_version(self) -> str:
        return self._agent_version

    async def invoke(
        self, scenario: Scenario, *, seed: int | None, timeout_s: float | None
    ) -> AgentResponse:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            msg = "http.json adapter requires httpx: pip install 'graines-evalkit[http]'"
            raise RuntimeError(msg) from exc
        body = {
            "scenario_id": scenario.scenario_id,
            "inputs": scenario.inputs,
            "context": scenario.context,
            "seed": seed,
        }
        start = time.perf_counter()
        unknown = [TokenUsage(provider=self.provider, model=self.model, source=UsageSource.UNKNOWN)]
        async with httpx.AsyncClient(timeout=timeout_s, transport=self.transport) as client:
            try:
                resp = await client.post(self.url, json=body, headers=self.headers)
            except httpx.HTTPError as exc:
                return AgentResponse(
                    output=None,
                    usage=unknown,
                    latency_ms=(time.perf_counter() - start) * 1000,
                    agent_version=self._agent_version,
                    metadata={"error": f"http error: {type(exc).__name__}: {exc}"},
                )
        latency = (time.perf_counter() - start) * 1000
        if resp.status_code >= 400:
            return AgentResponse(
                output=None,
                usage=unknown,
                latency_ms=latency,
                agent_version=self._agent_version,
                metadata={"error": f"http status {resp.status_code}"},
            )
        try:
            data = resp.json()
        except ValueError:
            return AgentResponse(
                output=None,
                usage=unknown,
                latency_ms=latency,
                agent_version=self._agent_version,
                metadata={"error": "non-JSON response"},
            )
        if not isinstance(data, dict):
            data = {"output": data}
        usage = [TokenUsage.model_validate(u) for u in data.get("usage") or []] or unknown
        steps = list(data.get("steps") or [])
        meta: dict[str, Any] = {}
        if data.get("error"):
            meta["error"] = str(data["error"])
        return AgentResponse(
            output=data.get("output"),
            usage=usage,
            trajectory_steps=steps,
            latency_ms=latency,
            agent_version=str(data.get("agent_version") or self._agent_version),
            metadata=meta,
        )
