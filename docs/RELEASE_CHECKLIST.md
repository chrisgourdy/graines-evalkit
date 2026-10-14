# Release checklist — V1 (0.1.0)

State on 2026-10-14 after Phase 8. Each line is a fact with its evidence; nothing below
publishes anything. Publication (PyPI, npm, registry, GitHub) is a level-4 action that only
Christophe can trigger, item by item.

| # | Item (`docs/RELEASE_POLICY.md`) | State | Evidence |
|---|---|---|---|
| 1 | ruff + mypy --strict + pytest green | done | `evalkit acceptance run` → 134 test functions, 0 failures (`docs/evidence/acceptance-junit.xml`) |
| 2 | Acceptance: 30 scenarios, criteria pre-defined, results with evidence | done — 29 PASS, 1 BLOCKED | `docs/ACCEPTANCE_REPORT.md` |
| 3 | Changelog up to date | done | `CHANGELOG.md` `[Unreleased]` → to be renamed `0.1.0` at tag time |
| 4 | Contract schema version | 1.0.0, unchanged since Phase 1 | `evalkit export-schemas` diff against `schemas/` empty |
| 5 | Migrations numbered, applied by `db migrate`, backup before migrate documented | done (0001–0004) | `docs/RUNBOOK.md`; downgrades: none written — each migration is additive (new tables/columns), documented reason |
| 6 | Compatibility CLI ↔ API ↔ SDK | done | `tests/test_compat.py` on a live server |
| 7 | pip-audit | no known vulnerabilities | run 2026-10-14 (`.venv/bin/pip-audit --skip-editable`) |
| 8 | npm audit (SDK, prod deps) | 0 vulnerabilities | run 2026-10-14 |
| 9 | SBOM | generated | `sh scripts/sbom.sh` → `dist/sbom/evalkit-python.cdx.json` (not committed: `dist/` ignored; CI job `sbom` uploads it) |
| 10 | Wheel installs in a clean venv and runs the demo | done | `tests/test_distribution.py` (scenario 22) |
| 11 | Docker image built and smoke-tested | **blocked** | no daemon here; CI job `docker` (EK-0030) once the repository is linked |
| 12 | CI pipeline executed at least once | **blocked** | no remote yet (EK-0005) |
| 13 | Rollback: previous wheel/image/tag available; data restore procedure | restore done, previous artifacts n/a for a first release | `evalkit db backup|restore`, `tests/test_autonomy.py` |
| 14 | Version bump `0.1.0.dev0` → `0.1.0` and git tag | **human decision** | `pyproject.toml`, `src/evalkit/__init__.py`, `sdk/typescript/package.json` |
| 15 | Publication PyPI / npm / Docker registry / GitHub | **not done — level 4** | requires explicit authorisation, item by item |

What a release does *not* claim: any validation on a real LLM provider (no key available;
adapters `anthropic`/`openai` are not written, EK-0019), real tariffs (EK-0017), a scheduler
run on a real cron/container (EK-0030), cron expressions or notifications (EK-0035/0036).
