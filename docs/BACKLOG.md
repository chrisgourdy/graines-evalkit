# Backlog

Structured registry. Once Phase 6 lands, tickets live in the SQLite store and this file is a
generated export; until then it is maintained by hand. Format: id · priority (1 = highest) ·
status · title · notes.

| Id | P | Status | Title | Notes |
|---|---|---|---|---|
| EK-0001 | 1 | CLOSED | Phase 2 — storage SQLite/JSONL/artifacts with migrations and locks | needed by every other module |
| EK-0002 | 1 | CLOSED | Phase 2 — sim.deterministic and sim.stochastic adapters | tests without any provider |
| EK-0003 | 1 | CLOSED | Phase 2 — deterministic evaluators (exact, normalised, json_schema, regex, required_keys, numeric_tolerance, trace rules) | |
| EK-0004 | 1 | CLOSED | Phase 2 — orchestrator + `evalkit run` + JSON/Markdown report | end-to-end MVP |
| EK-0005 | 2 | OPEN | Link GitHub account and create remote repo (needs explicit authorisation) | unblocks CI and Docker builds |
| EK-0006 | 2 | OPEN | Decide licence before any external release | currently Proprietary |
| EK-0007 | 2 | OPEN | Provider usage conventions catalogue with real payload fixtures (Anthropic, OpenAI) | subsets declaration |
| EK-0008 | 3 | CLOSED | Chart library decision (Chart.js vs ECharts) with ADR | ADR-0007: server-rendered SVG |
| EK-0009 | 3 | OPEN | Obtain API keys for separate real-integration test runs | adapters stay NT otherwise |
| EK-0010 | 3 | OPEN | SBOM generation (CycloneDX) in release pipeline | |
| EK-0011 | 1 | CLOSED | Phase 3 — statistical engine (Wilson, Clopper-Pearson, BCa bootstrap, paired comparison, Holm, INCONCLUSIVE rules, seeded property tests) | |
| EK-0012 | 1 | CLOSED | Phase 3 — TOKEN_METER usage table (migration 0002), attribution, provider subset conventions | |
| EK-0013 | 1 | CLOSED | Phase 3 — COST_CONTROLLER: price registry seed, forecast from history, atomic reservations, caps, concurrency test | unblocks cost-bearing adapters |
| EK-0014 | 2 | CLOSED | Orchestrator concurrency (bounded workers) once reservations exist | sequential in Phase 2 |
| EK-0015 | 2 | OPEN | Campaign resume (`campaign resume`) using persisted runs | Phase 7, groundwork exists (runs saved progressively) |
| EK-0016 | 3 | CLOSED | `http.json` adapter (httpx, optional dep) | moved from Phase 2 |
| EK-0017 | 2 | OPEN | Seed real provider tariffs with source URL + verification date (never fabricated) | registry ships `sim` + template only |
| EK-0018 | 1 | CLOSED | Phase 4 — SCORING_ENGINE scorecards, weights, validity controls | |
| EK-0019 | 1 | CLOSED | Phase 4 — HTML report + dashboard pages + CSV export; chart library ADR | |
| EK-0020 | 3 | OPEN | TOST equivalence test with declared margin | V1.1 |
| EK-0021 | 3 | OPEN | Cluster bootstrap by scenario for campaign-level intervals | currently flagged in validity notes |
| EK-0022 | 3 | OPEN | OpenTelemetry bridge (export events, ingest OTLP traces) | optional dep `otel` |
| EK-0023 | 3 | OPEN | Report pagination/aggregation for campaigns with hundreds of scenarios | SVG pages grow linearly |
| EK-0024 | 1 | CLOSED | Phase 5 — wheel build + clean venv install test; Dockerfile + compose; CI multi-arch build | |
| EK-0025 | 1 | CLOSED | Phase 5 — HTTP API `/v1` (FastAPI) over core; API-key auth; local bind by default | |
| EK-0026 | 1 | CLOSED | Phase 5 — npm `@graines/evalkit` SDK (types from schemas, client, event/trace push); compat tests | |
| EK-0028 | 1 | CLOSED | Phase 6 — ticket runtime, incident detection, dedup with history, BACKLOG.md export | done 2026-10-14 (`feedback/tickets.py`, `evalkit tickets`, `backlog export`) |
| EK-0029 | 1 | CLOSED | Phase 6 — retrofit cycle on simulated regression, learnings KB, self-evaluation scorecard | done 2026-10-14 (`improvement/`, `evalkit retrofit`, `learnings`, `self-check`) |
| EK-0032 | 3 | OPEN | Retrofit: when a cycle validates a fix, sibling tickets of the same campaign (other scenarios/regressions) stay OPEN; link them to the validated ticket | V1.1 |
| EK-0033 | 2 | CLOSED | Phase 7: apply a validated low-risk fix inside the level-3 perimeter (write `evalkit.yaml`, rollback, audit) | done 2026-10-14 (`improvement/apply.py`, scheduler) |
| EK-0035 | 3 | OPEN | Scheduler: per-job notification hook (webhook/e-mail) on pause, apply or rollback | V1.1 |
| EK-0036 | 3 | OPEN | Scheduler: cron expressions in addition to `interval_minutes` | V1.1 |
| EK-0037 | 2 | OPEN | Phase 8: acceptance report `docs/ACCEPTANCE_REPORT.md` generated from test evidence (ids, logs, paths) | |
| EK-0034 | 4 | OPEN | Diagnosis hypotheses from an LLM (optional, provider required, clearly labelled as such) | V2 |
| EK-0030 | 2 | OPEN | Run the CI docker job once the GitHub repo exists; record image digest in STATUS | blocked by EK-0005 |
| EK-0031 | 3 | OPEN | API: pagination and filters on list endpoints; rate limiting | V1.1 |
| EK-0027 | 3 | OPEN | Scorecard: suppress 'underpowered' warning for deterministic adapters at n=1 when the dimension is fully deterministic | currently honest but noisy |
