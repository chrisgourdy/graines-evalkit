# Learnings

Verified, provenance-tracked knowledge. Each entry: date · scope · statement · evidence ·
validation status (`observed` → `verified` → `adopted` | `rejected`). Nothing here is a
rule until `adopted`. Per-project learnings live in the store (`learnings` table) and are
exported with `evalkit learnings export --project <id>`; this file keeps the project-wide
entries of EVALKIT itself.

| Date | Scope | Statement | Evidence | Status |
|---|---|---|---|---|
| 2026-10-13 | distribution | `evalkit` is taken on PyPI and npm; use `graines-evalkit` / `@graines/evalkit` | registry lookups (Phase 0) | adopted |
| 2026-10-13 | environment | Docker images cannot be built in the Cowork dev environment; CI is the only build path | Phase 0 audit | adopted |
| 2026-10-14 | improvement | On the demo project a DEVELOPMENT-only candidate has n=2 paired scenarios: the comparison vs the broken campaign is always underpowered, so the decision relies on absence of eliminatory failure + no regression vs good, not on a significant improvement | `tests/test_improvement.py::test_retrofit_cycle_reverts_simulated_regression` | verified |
