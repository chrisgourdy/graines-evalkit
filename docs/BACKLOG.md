# Backlog

Structured registry. Once Phase 6 lands, tickets live in the SQLite store and this file is a
generated export; until then it is maintained by hand. Format: id · priority (1 = highest) ·
status · title · notes.

| Id | P | Status | Title | Notes |
|---|---|---|---|---|
| EK-0001 | 1 | OPEN | Phase 2 — storage SQLite/JSONL/artifacts with migrations and locks | needed by every other module |
| EK-0002 | 1 | OPEN | Phase 2 — sim.deterministic and sim.stochastic adapters | tests without any provider |
| EK-0003 | 1 | OPEN | Phase 2 — deterministic evaluators (exact, normalised, json_schema, regex, required_keys, numeric_tolerance, trace rules) | |
| EK-0004 | 1 | OPEN | Phase 2 — orchestrator + `evalkit run` + JSON/Markdown report | end-to-end MVP |
| EK-0005 | 2 | OPEN | Link GitHub account and create remote repo (needs explicit authorisation) | unblocks CI and Docker builds |
| EK-0006 | 2 | OPEN | Decide licence before any external release | currently Proprietary |
| EK-0007 | 2 | OPEN | Provider usage conventions catalogue with real payload fixtures (Anthropic, OpenAI) | subsets declaration |
| EK-0008 | 3 | OPEN | Chart library decision (Chart.js vs ECharts) with ADR | Phase 4 |
| EK-0009 | 3 | OPEN | Obtain API keys for separate real-integration test runs | adapters stay NT otherwise |
| EK-0010 | 3 | OPEN | SBOM generation (CycloneDX) in release pipeline | |
