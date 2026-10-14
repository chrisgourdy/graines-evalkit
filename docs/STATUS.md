# Status — implemented vs verified

Updated: 2026-10-14 (end of Phase 6).

Legend: **IV** implemented & verified (automated test exists and passes) · **IP** implemented,
partially verified · **SIM** validated only with simulated agents · **NT** implemented, not
tested · **PL** planned · **BL** blocked.

| Capability | Status | Evidence |
|---|---|---|
| Public contracts, JSON Schema export, double-count-safe usage | IV | `tests/test_contracts.py` |
| Documentation set + consistency test | IV | `tests/test_docs_consistency.py` |
| SQLite storage: migrations (0001, 0002, 0003), transactions, artifacts | IV | `tests/test_storage.py` |
| Audit trail append-only, hash chain, corrections, JSONL export | IV | `tests/test_storage.py` |
| Secret redaction in events | IP | key-name based only |
| Project + scenario loader | IV | `tests/test_orchestrator.py` |
| Adapters `sim.*`, `python.callable` | IV / SIM | `tests/test_adapters_evaluators.py` |
| Adapter `http.json` | IV (mock transport) | `tests/test_http_adapter.py` |
| Eight deterministic evaluators | IV | `tests/test_adapters_evaluators.py` |
| Orchestrator: profiles, DRY_RUN, seeds, eliminatory stop, bounded workers, reservations | IV / SIM | `tests/test_orchestrator.py`, `tests/test_cost_controller.py` |
| Statistical engine | IV | `tests/test_stats.py` |
| TOKEN_METER | IV | `tests/test_token_meter.py` |
| Provider conventions Anthropic/OpenAI (subsets) | IP | fixtures follow documented shapes (EK-0007) |
| Cost computation, price registry (synthetic `sim` only), forecast | IV | `tests/test_cost_controller.py`; real tariffs EK-0017 |
| Budgets, atomic reservations, 12-thread cap proof, STOPPED_BUDGET | IV / SIM | `tests/test_cost_controller.py` |
| SCORING_ENGINE, validity controls | IV / SIM | `tests/test_scoring_reporting.py` |
| Overfitting signal DEVELOPMENT vs HOLDOUT | IP | no dedicated positive test |
| Reports JSON/Markdown/HTML, dashboard, CSV | IV / SIM | `tests/test_scoring_reporting.py` |
| HTTP API `/v1` (auth, launch/poll, results, scorecard, report, events, usage/event push) | IV / SIM | `tests/test_api.py` (TestClient), `tests/test_compat.py` (live uvicorn) |
| TypeScript SDK `@graines/evalkit` | IV | `sdk/typescript/test` (fake fetch) + SDK leg of `tests/test_compat.py` (real server, node) |
| CLI ↔ API ↔ SDK compatibility | IV / SIM | `tests/test_compat.py` — identical report shape across the three paths |
| Wheel build + clean-venv install + demo run | IV (manual + CI job) | executed in Phase 5 on Python 3.13; CI job `wheel` |
| Docker image (Dockerfile, entrypoint, compose) | IP / BL | statically validated (compose parses, non-root, `sh -n`); never built — no daemon here; CI job `docker` runs once the repo is linked (EK-0030) |
| CI pipeline (python matrix, wheel, sdk, docker, sbom) | NT | YAML valid; never executed (no remote yet) |
| SBOM (CycloneDX 1.6) | IV (manual) | `scripts/sbom.sh` produced 93 components locally |
| Real provider adapters (Anthropic/OpenAI) | BL | no API key available |
| OTel bridge | PL | EK-0022 |
| Governance policy engine (levels, ALWAYS_HUMAN, agent actors capped) | IV | `tests/test_improvement.py` |
| Ticket runtime: incident detection, structured tickets, dedup with history, workflow 1.0.0 | IV / SIM | `tests/test_improvement.py` (scenarios 18, 19) |
| Retrofit cycle OBSERVE→…→LEARN, isolated copy without HOLDOUT, decision by policy, experiments table | IV / SIM | `tests/test_improvement.py` (scenario 20): revert fix accepted, useless fix rejected, agent actor never applies, decided ticket never reworked |
| Learning confirmation on DEEP campaign with HOLDOUT (`retrofit confirm`) | IV / SIM | `tests/test_improvement.py` |
| Learnings KB with provenance and status | IV | `tests/test_improvement.py`; `docs/LEARNINGS.md` export |
| Self-evaluation scorecard of EVALKIT | IV | `tests/test_improvement.py` (scenario 21); `evalkit self-check` |
| Automatic application of a validated fix to the real project | PL | the cycle decides, never writes the project; level 3 perimeter is checked in code but applying stays manual (EK-0033) |
| Rule-based diagnosis only (config/version diff); no LLM hypotheses | by design | EK-0034 (V2) |
| Scheduler, autonomy policies, resume | PL | Phase 7 (`scheduler` image mode exits 64) |
| Acceptance report (30 scenarios) | PL | Phase 8 — covering tests now exist for 1, 2, 5–22, 24, 25, 28, 29; 23 blocked on CI |
| External publication (PyPI, npm, registry, GitHub) | not done | requires explicit authorisation (level 4) |
