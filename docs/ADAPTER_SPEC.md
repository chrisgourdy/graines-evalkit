# Adapter specification

Port: `evalkit.adapters.AgentAdapter`; capabilities: `AdapterCapabilities`.

## 1. Contract

An adapter targets one agent version and implements
`async invoke(scenario, *, seed, timeout_s) -> AgentResponse`.

- `scenario.inputs` are passed to the agent; `scenario.context` provides fixtures.
- The response carries the output (any JSON value), one `TokenUsage` per LLM call with its
  `source`, trajectory steps (if `reports_trajectory`), latency and metadata.
- Agent-level failures are returned (metadata `error`), adapter faults are raised.
- The output is untrusted: adapters must not evaluate, interpret or act on it.

## 2. Capabilities must be honest

`reports_usage=False` forces the meter to ESTIMATED/UNKNOWN. `deterministic=True` lets the
engine skip repetitions. `cost_bearing=False` exempts the adapter from budget reservations
(simulated agents, local models with no billing).

## 3. Reference adapters

| Adapter | Phase | Purpose |
|---|---|---|
| `sim.deterministic` | 2 (done) | behaviours reference/wrong/fixed/error, REPORTED synthetic usage (or UNKNOWN) |
| `sim.stochastic` | 2 (done) | seeded p_wrong/p_error/p_retry, latency jitter, retry/error steps |
| `http.json` | 3 (done) | POST scenario to any HTTP endpoint; response is untrusted; usage UNKNOWN unless returned |
| `python.callable` | 2 (done) | wrap an in-process callable; usage UNKNOWN unless returned |
| `anthropic.messages` | 3 | real provider (needs key; integration tests only) |
| `openai.chat` | 3 | real provider (needs key; integration tests only) |
| `otlp.ingest` | V1.1 | build trajectories from OTLP traces |

## 4. Writing an adapter

1. Implement the port; declare capabilities truthfully.
2. Map provider usage payloads to `TokenUsage` with `subsets` declared.
3. Emit trajectory steps for tool calls, retries and errors.
4. Add a fixture-based test (no network) and, if real, an `integration`-marked test.
