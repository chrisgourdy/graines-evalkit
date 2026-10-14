# Status — implemented vs verified

Updated: 2026-10-14 (end of Phase 2).

Legend: **IV** implemented & verified (automated test exists and passes) · **IP** implemented,
partially verified · **SIM** validated only with simulated agents · **NT** implemented, not
tested · **PL** planned · **BL** blocked.

| Capability | Status | Evidence |
|---|---|---|
| Public contracts (pydantic, versioned) | IV | `tests/test_contracts.py` |
| JSON Schema export | IV | `tests/test_contracts.py::test_schema_export` |
| Token usage double-count-safe total | IV | `tests/test_contracts.py::test_billable_total_*` |
| Documentation set + consistency test | IV | `tests/test_docs_consistency.py` |
| SQLite storage: migrations, transactions, artifacts | IV | `tests/test_storage.py` |
| Audit trail append-only, hash chain, corrections, JSONL export | IV | `tests/test_storage.py` (tamper test) |
| Secret redaction in events | IP | `tests/test_storage.py::test_redaction_in_events` (key-name based only) |
| Project + scenario loader (schema-validated, loud failures) | IV | `tests/test_orchestrator.py` |
| Adapters `sim.deterministic`, `sim.stochastic`, `python.callable` | IV / SIM | `tests/test_adapters_evaluators.py` |
| Evaluators exact/normalized/json_schema/regex/required_keys/numeric_tolerance/max_length/trace_rules | IV | `tests/test_adapters_evaluators.py` |
| Orchestrator: profiles, DRY_RUN, seeds, eliminatory stop, refusal of cost-bearing adapters | IV / SIM | `tests/test_orchestrator.py` |
| Chronology reconstruction from audit events | IV | `test_audit_chronology_reconstructs_campaign` |
| Two-project isolation | IV | `test_two_projects_are_isolated` |
| JSON + Markdown campaign report | IV | `test_report_files_written` |
| CLI run/report/campaigns/db/scenarios | IV | `tests/test_orchestrator.py::test_cli_run_report_check`, `tests/test_cli.py` |
| Statistics, confidence intervals, Monte-Carlo | PL | Phase 3 |
| TOKEN_METER aggregation tables, attribution | PL | Phase 3 (usage is stored per run and audited) |
| COST_CONTROLLER, price registry, reservations | PL | Phase 3 (cost-bearing adapters refused until then) |
| Scoring, scorecards, HTML reporting | PL | Phase 4 |
| Docker image build/test | BL | no Docker daemon in dev env → CI once repo is linked |
| PyPI package build | PL | Phase 5 |
| npm SDK | PL | Phase 5 |
| Real provider adapters (Anthropic/OpenAI), `http.json` | BL / PL | no API key available |
| Backlog, retrofit cycle, learnings runtime | PL | Phase 6 |
| Scheduler, autonomy policies, resume | PL | Phase 7 |
| Acceptance report (30 scenarios) | PL | Phase 8 — scenarios 1, 2, 9, 15, 25, 28, 29 already have covering tests (not yet the formal report) |
