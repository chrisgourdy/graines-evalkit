# Release checklist — V1 (0.1.0)

State on 2026-10-14 after Phase 8 and the first CI run (private repository `chrisgourdy/graines-evalkit`, run 38576929393 on commit 7eb20b3: 8 jobs green). Each line is a fact with its evidence; nothing below
publishes anything. Publication (PyPI, npm, registry, GitHub) is a level-4 action that only
Christophe can trigger, item by item.

| # | Item (`docs/RELEASE_POLICY.md`) | State | Evidence |
|---|---|---|---|
| 1 | ruff + mypy --strict + pytest green | done | `evalkit acceptance run` → 134 test functions, 0 failures (`docs/evidence/acceptance-junit.xml`) |
| 2 | Acceptance: 30 scenarios, criteria pre-defined, results with evidence | done — 30 PASS, 0 BLOCKED, 0 FAIL | `docs/ACCEPTANCE_REPORT.md`; scenario 23 on `docs/evidence/ci-docker.json` |
| 3 | Changelog up to date | done | `CHANGELOG.md` `[Unreleased]` → to be renamed `0.1.0` at tag time |
| 4 | Contract schema version | 1.0.0, unchanged since Phase 1 | `evalkit export-schemas` diff against `schemas/` empty |
| 5 | Migrations numbered, applied by `db migrate`, backup before migrate documented | done (0001–0004) | `docs/RUNBOOK.md`; downgrades: none written — each migration is additive (new tables/columns), documented reason |
| 6 | Compatibility CLI ↔ API ↔ SDK | done | `tests/test_compat.py` on a live server |
| 7 | pip-audit | no known vulnerabilities | run 2026-10-14 (`.venv/bin/pip-audit --skip-editable`) |
| 8 | npm audit (SDK, prod deps) | 0 vulnerabilities | run 2026-10-14 |
| 9 | SBOM | generated | CI artifact `sbom` (11.7 KB) of run 38576929393; locally `sh scripts/sbom.sh` |
| 10 | Wheel installs in a clean venv and runs the demo | done | `tests/test_distribution.py` (scenario 22) |
| 11 | Docker image built and smoke-tested | done | CI job `docker` (5m02s): multi-arch build, amd64 smoke test with persistent volume, evidence artifact `docker-evidence` (https://github.com/chrisgourdy/graines-evalkit/actions/runs/38576929393) |
| 12 | CI pipeline executed at least once | done | run #1 green: python ×3, acceptance, wheel, sdk, docker, sbom (https://github.com/chrisgourdy/graines-evalkit/actions/runs/38576929393) |
| 13 | Rollback: previous wheel/image/tag available; data restore procedure | restore done, previous artifacts n/a for a first release | `evalkit db backup|restore`, `tests/test_autonomy.py` |
| 14 | Version bump `0.1.0.dev0` → `0.1.0` and git tag | **human decision** | `pyproject.toml`, `src/evalkit/__init__.py`, `sdk/typescript/package.json` |
| 15 | Publication PyPI / npm / Docker registry | **not done — level 4** | requires explicit authorisation, item by item; the GitHub repository is private and holds no release or tag |

What a release does *not* claim: any validation on a real LLM provider (no key available;
adapters `anthropic`/`openai` are not written, EK-0019) — every PASS, the container smoke test
included, runs simulated agents; real tariffs (EK-0017); a scheduler run on a real cron or a
long-lived container (the CI smoke test exercises `worker` mode only); cron expressions or
notifications (EK-0035/0036); the prompt-injection protection is structural (outputs are data)
plus a heuristic marker scan — not a classifier, and not a guarantee against novel phrasings.
