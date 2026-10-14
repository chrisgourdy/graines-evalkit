# Status — implemented vs verified

Updated: 2026-10-14 (end of Phase 3).

Legend: **IV** implemented & verified (automated test exists and passes) · **IP** implemented,
partially verified · **SIM** validated only with simulated agents · **NT** implemented, not
tested · **PL** planned · **BL** blocked.

| Capability | Status | Evidence |
|---|---|---|
| Public contracts, JSON Schema export, double-count-safe usage | IV | `tests/test_contracts.py` |
| Documentation set + consistency test | IV | `tests/test_docs_consistency.py` |
| SQLite storage: migrations (0001, 0002), transactions, artifacts | IV | `tests/test_storage.py` |
| Audit trail append-only, hash chain, corrections, JSONL export | IV | `tests/test_storage.py` |
| Secret redaction in events | IP | key-name based only |
| Project + scenario loader | IV | `tests/test_orchestrator.py` |
| Adapters `sim.*`, `python.callable` | IV / SIM | `tests/test_adapters_evaluators.py` |
| Adapter `http.json` | IV (mock transport) | `tests/test_http_adapter.py` — no real endpoint exercised |
| Eight deterministic evaluators | IV | `tests/test_adapters_evaluators.py` |
| Orchestrator: profiles, DRY_RUN, seeds, eliminatory stop, bounded workers | IV / SIM | `tests/test_orchestrator.py`, `tests/test_cost_controller.py` |
| Statistical engine: Wilson/CP/Jeffreys/rule-of-three, t, BCa bootstrap | IV | `tests/test_stats.py` (10 000-sim coverage tests) |
| Paired / unpaired comparisons, INCONCLUSIVE rules, effect sizes, Holm | IV | `tests/test_stats.py` |
| Seeded stratified sampling, dispersion, failure rate, variance decomposition | IV | `tests/test_stats.py` |
| TOKEN_METER: records, attribution, aggregation statuses, history | IV | `tests/test_token_meter.py` |
| Provider conventions Anthropic/OpenAI (subsets) | IP | fixtures follow documented shapes, not live payloads (EK-0007) |
| Cost computation (subsets, unknown price → UNKNOWN, estimated, native units) | IV | `tests/test_cost_controller.py` |
| Price registry import/lookup (synthetic `sim` tariff only) | IV | `tests/test_cost_controller.py`; real tariffs: EK-0017 |
| Forecast (history p90 / conservative default) | IV | `tests/test_cost_controller.py` |
| Budgets, atomic reservations, settle/release, thresholds, no-budget block | IV | `tests/test_cost_controller.py` |
| Concurrent reservations cannot exceed cap | IV | `test_concurrent_reservations_cannot_exceed_cap` (12 threads, own connections) |
| Campaign stopped on budget (STOPPED_BUDGET) | IV / SIM | `test_paid_campaign_meters_costs_and_stops_on_budget` |
| Report v1.1: CIs, usage/cost status, cost per valid run, baseline comparison | IV | `tests/test_orchestrator.py::test_report_files_written` + CLI demo |
| CLI compare / budget / prices | IP | exercised manually; `budget`/`prices` lack dedicated CLI tests |
| Scoring, scorecards, HTML reporting, dashboard | PL | Phase 4 |
| Docker image build/test | BL | no Docker daemon in dev env → CI once repo is linked |
| PyPI package build, npm SDK | PL | Phase 5 |
| Real provider adapters (Anthropic/OpenAI) | BL | no API key available |
| OTel bridge | PL | EK-0022 |
| Backlog, retrofit cycle, learnings runtime | PL | Phase 6 |
| Scheduler, autonomy policies, resume | PL | Phase 7 (`release_stale` groundwork exists) |
| Acceptance report (30 scenarios) | PL | Phase 8 — covering tests now exist for 1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 25, 28, 29 |
