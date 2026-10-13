# Status — implemented vs verified

Updated: 2026-10-13 (end of Phase 1).

Legend: **IV** implemented & verified (automated test exists and passes) · **IP** implemented,
partially verified · **SIM** validated only with simulated agents · **NT** implemented, not
tested · **PL** planned · **BL** blocked.

| Capability | Status | Evidence |
|---|---|---|
| Public contracts (pydantic, versioned) | IV | `tests/test_contracts.py` |
| JSON Schema export | IV | `tests/test_contracts.py::test_schema_export` |
| Token usage double-count-safe total | IV | `tests/test_contracts.py::test_billable_total_*` |
| Module ports (`interfaces.py`) | IP | type-checked (mypy strict), no runtime use yet |
| CLI (`version`, `export-schemas`) | IV | `tests/test_cli.py` |
| Documentation set + consistency test | IV | `tests/test_docs_consistency.py` |
| Storage (SQLite/JSONL/artifacts) | PL | Phase 2 |
| Simulated adapters | PL | Phase 2 |
| Deterministic evaluators | PL | Phase 2 |
| Orchestrator, first persisted report | PL | Phase 2 |
| Statistics, Monte-Carlo | PL | Phase 3 |
| TOKEN_METER, COST_CONTROLLER, AUDIT_TRAIL runtime | PL | Phase 3 |
| Scoring, HTML reporting | PL | Phase 4 |
| Docker image build/test | BL | no Docker daemon in dev env → CI (GitHub Actions) once repo is linked |
| PyPI package build | PL | Phase 5 (local wheel build is possible) |
| npm SDK | PL | Phase 5 |
| Real provider adapters (Anthropic/OpenAI) | BL | no API key available; will be NT until a key is supplied |
| Backlog, retrofit cycle, learnings | PL | Phase 6 |
| Scheduler, autonomy policies | PL | Phase 7 |
| Acceptance report (30 scenarios) | PL | Phase 8 |
