# Status — implemented vs verified

Updated: 2026-10-14 (end of Phase 4).

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
| Orchestrator: profiles, DRY_RUN, seeds, eliminatory stop, bounded workers, reservations | IV / SIM | `tests/test_orchestrator.py`, `tests/test_cost_controller.py` |
| Statistical engine (intervals, bootstrap, comparisons, Holm, sampling, variance) | IV | `tests/test_stats.py` (10 000-sim coverage) |
| TOKEN_METER records/attribution/aggregation/history | IV | `tests/test_token_meter.py` |
| Provider conventions Anthropic/OpenAI (subsets) | IP | fixtures follow documented shapes, not live payloads (EK-0007) |
| Cost computation, price registry (synthetic `sim` only), forecast | IV | `tests/test_cost_controller.py`; real tariffs: EK-0017 |
| Budgets, atomic reservations, thresholds, 12-thread cap proof, STOPPED_BUDGET | IV / SIM | `tests/test_cost_controller.py` |
| SCORING_ENGINE: scorecards, eliminatory independence, aggregate formula, validity controls | IV / SIM | `tests/test_scoring_reporting.py` |
| Overfitting signal DEVELOPMENT vs HOLDOUT | IP | code path exists; demo data rarely triggers it (no dedicated positive test yet) |
| Report v1.1 JSON/Markdown (CIs, cost, baseline comparison) | IV | `tests/test_orchestrator.py::test_report_files_written` |
| HTML campaign report + static dashboard (inline SVG, no script) | IV / SIM | `tests/test_scoring_reporting.py` (values asserted against store), visual check via headless Chromium during Phase 4 |
| CSV exports | IV | `tests/test_scoring_reporting.py::test_csv_exports` |
| CLI run/report/compare/budget/prices/scorecard/dashboard/db/scenarios | IV / IP | `tests/test_scoring_reporting.py::test_cli_scorecard_and_dashboard`, `tests/test_orchestrator.py`; `budget`/`prices` CLI exercised manually only |
| Docker image build/test | BL | no Docker daemon in dev env → CI once repo is linked |
| PyPI package build, HTTP API, npm SDK | PL | Phase 5 |
| Real provider adapters (Anthropic/OpenAI) | BL | no API key available |
| OTel bridge | PL | EK-0022 |
| Backlog/ticket runtime, retrofit cycle, learnings | PL | Phase 6 (improvement page shows stored tickets when they exist) |
| Scheduler, autonomy policies, resume | PL | Phase 7 (`release_stale` groundwork exists) |
| Acceptance report (30 scenarios) | PL | Phase 8 — covering tests now exist for 1, 2, 5–17, 25, 28, 29 |
