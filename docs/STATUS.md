# Status — implemented vs verified

Updated: 2026-10-14 (tag v0.1.0, after two green CI runs: 38576929393 on 7eb20b3, 38579832916 on e1be980).

Legend: **IV** implemented & verified (automated test exists and passes) · **IP** implemented,
partially verified · **SIM** validated only with simulated agents · **NT** implemented, not
tested · **PL** planned · **BL** blocked.

| Capability | Status | Evidence |
|---|---|---|
| Public contracts, JSON Schema export, double-count-safe usage | IV | `tests/test_contracts.py` |
| Documentation set + consistency test | IV | `tests/test_docs_consistency.py` |
| SQLite storage: migrations (0001–0004), transactions, artifacts | IV | `tests/test_storage.py` |
| Backup (online, manifest) / restore (integrity + chain checks, refusals) | IV | `tests/test_autonomy.py` |
| Audit trail append-only, hash chain, corrections, JSONL export | IV | `tests/test_storage.py` |
| Secret redaction in events | IP | key-name based only |
| Project + scenario loader | IV | `tests/test_orchestrator.py` |
| Adapters `sim.*`, `python.callable` | IV / SIM | `tests/test_adapters_evaluators.py` |
| Adapter `http.json` | IV (mock transport) | `tests/test_http_adapter.py` |
| Nine deterministic evaluators (incl. `injection_guard`) | IV | `tests/test_adapters_evaluators.py` |
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
| Wheel build + clean-venv install + demo run | IV | `tests/test_distribution.py` (integration_local); CI job `wheel` |
| Docker image (Dockerfile, entrypoint, compose) | IV / SIM | built in CI for linux/amd64 + linux/arm64 (run 38576929393 digest `sha256:1191d5a9…`, run 38579832916 digest `sha256:bb56784e…` — not byte-reproducible), smoke-tested in containers on a persistent volume: campaign COMPLETED, scorecard PASS, `db check` OK, `self-check` PASS; evidence `docs/evidence/ci-docker.json` + artifact `docker-evidence` (https://github.com/chrisgourdy/graines-evalkit/actions/runs/38576929393); compose demo still never run |
| CI pipeline (python 3.11/3.12/3.13, acceptance, wheel, sdk, docker, sbom) | IV | two green runs: 7eb20b3 (38576929393, 5m06s) and e1be980 (38579832916, 4m45s), 8 jobs and 6 artifacts each |
| SBOM (CycloneDX 1.6) | IV (manual) | `scripts/sbom.sh` produced 93 components locally |
| Real provider adapters (Anthropic/OpenAI) | BL | no API key available |
| OTel bridge | PL | EK-0022 |
| Governance policy engine (levels, ALWAYS_HUMAN, agent actors capped) | IV | `tests/test_improvement.py` |
| Ticket runtime: incident detection, structured tickets, dedup with history, workflow 1.0.0 | IV / SIM | `tests/test_improvement.py` (scenarios 18, 19) |
| Retrofit cycle OBSERVE→…→LEARN, isolated copy without HOLDOUT, decision by policy, experiments table | IV / SIM | `tests/test_improvement.py` (scenario 20): revert fix accepted, useless fix rejected, agent actor never applies, decided ticket never reworked |
| Learning confirmation on DEEP campaign with HOLDOUT (`retrofit confirm`) | IV / SIM | `tests/test_improvement.py` |
| Learnings KB with provenance and status | IV | `tests/test_improvement.py`; `docs/LEARNINGS.md` export |
| Self-evaluation scorecard of EVALKIT | IV | `tests/test_improvement.py` (scenario 21); `evalkit self-check` |
| Controlled apply of an APPLY_ALLOWED fix + rollback (backups, policy re-checked at apply time) | IV / SIM | `tests/test_autonomy.py` (EK-0033 closed) |
| Rule-based diagnosis only (config/version diff); no LLM hypotheses | by design | EK-0034 (V2) |
| Campaign resume after interruption (stuck runs cancelled, reservations released, attempts re-planned) | IV / SIM | `tests/test_autonomy.py` (scenario 26) |
| Scheduler: YAML plan, durable state, due/interval, last_good baseline, campaign cost cap, unattended retrofit → apply → confirm → rollback, guards (per-day, cool-down, consecutive failures → pause + human resume), exclusive lock, auto-resume | IV / SIM | `tests/test_autonomy.py`; image `scheduler` mode wired (never built, EK-0030) |
| Scheduler on a real cron/systemd/container | NT | wiring exists (image mode `scheduler`); not exercised by the CI smoke test (worker mode only). **Prerequisite before any autonomous use on a client project** (release checklist item 17) |
| Prompt-injection protection (structural + `injection_guard` detector) | IV / SIM | `tests/test_acceptance.py` (scenario 27) |
| Acceptance report generated from JUnit evidence (`evalkit acceptance run`) | IV | `docs/ACCEPTANCE_REPORT.md`: 30 PASS, 0 BLOCKED, 0 FAIL (scenario 23 judged on the CI evidence file); `tests/test_acceptance.py` (scenario 30); CI job `acceptance` reproduces it as artifact `acceptance-evidence` |
| Release checklist V1 | done except human-only items | `docs/RELEASE_CHECKLIST.md` |
| External publication (PyPI, npm, registry, GitHub) | not done | requires explicit authorisation (level 4) |
