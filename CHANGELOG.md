# Changelog

All notable changes to this project are documented here (Keep a Changelog, semver).

## [Unreleased]

### Added
- Phase 8 (acceptance): `acceptance/` package — registry of the 30 scenarios (criteria
  verbatim from `docs/ACCEPTANCE_SCENARIOS.md`, covering tests, modes simulated / whole
  suite / ci only), JUnit parsing, PASS / FAIL / BLOCKED / NOT_RUN decision, Markdown
  report; CLI `acceptance list|run`; `injection_guard` evaluator and `sim.deterministic`
  behaviour `injection` with demo agent `greeter-guarded` (scenario 27); wheel-install test
  (scenario 22, integration_local); `docs/ACCEPTANCE_REPORT.md` + `docs/evidence/`,
  `docs/RELEASE_CHECKLIST.md`.
- Phase 7 (autonomy): `CampaignRunner.resume` + CLI `campaign resume` (stuck runs kept as
  CANCELLED without error, reservations released, remaining attempts re-planned, audited);
  `SQLiteRepository.backup/restore` + CLI `db backup|restore` (online SQLite backup API,
  manifest, integrity and chain checks, refusals); controlled apply of an `APPLY_ALLOWED`
  fix with backups and rollback (`improvement/apply.py`, CLI `retrofit apply|rollback`,
  policy re-checked at apply time, EK-0033); scheduler (`scheduler/`: YAML plan, migration
  0004 `schedule_state`, due/interval, `last_good` baseline tracking, campaign cost cap,
  unattended retrofit → apply → DEEP confirm → rollback, guards: retrofits per day,
  cool-down, consecutive failures → pause + `human.intervention`, exclusive lock, automatic
  resume of an interrupted campaign; CLI `schedule run [--once]|status|resume-job`; Docker
  `scheduler` mode wired); example plan `scenarios/examples/schedule.example.yaml`; 15 tests.
- Phase 6 (continuous improvement): migration 0003 (`tickets.fingerprint/agent_id`,
  `learnings`, `experiments`); `governance.ProjectPolicyEngine` + `autonomy:` block in
  `evalkit.yaml` (levels enforced in code, `ALWAYS_HUMAN` kinds, `agent:*` actors never above
  level 2; `Action.required_level` now defaults to level 1 and can never lower a kind's level);
  `feedback.TicketStore` (incident detection from scorecards, structured tickets with
  evidence, fingerprint dedup with linked DUPLICATE tickets, workflow 1.0.0, audit events),
  `render_backlog_markdown`; `improvement.RetrofitCycle` (OBSERVE→…→LEARN on an isolated
  project copy without HOLDOUT, built-in fix providers, paired comparison, policy decision,
  `experiments` table, `confirm` on DEEP with HOLDOUT), `LearningStore`, `self_evaluate`;
  `campaign.started` events now carry the agent configuration; CLI `tickets`, `retrofit`,
  `learnings`, `backlog export`, `self-check`; 15 tests (acceptance scenarios 18–21).
- `docs/TUTORIEL.md`: user tutorial in French, linked from README and CLAUDE.md; the docs
  consistency test now requires it.
- Phase 5 (distribution): HTTP API `/v1` (FastAPI; `X-EvalKit-Key`, 503 when no key is
  configured, loopback bind, background campaign execution, usage/event push, schemas), CLI
  `api serve`, TypeScript SDK `@graines/evalkit` (types generated per schema, fetch client,
  `waitForCampaign`, OpenAI/Anthropic usage builders, node:test), wheel build + clean-venv
  install check, `docker/` (multi-stage non-root image, entrypoint modes cli/api/worker,
  compose demo, statically validated), CI jobs python/wheel/sdk/docker/sbom,
  `scripts/sbom.sh` (CycloneDX 1.6), compatibility test CLI ↔ API ↔ SDK on a live server.
- Phase 4 (scoring & visualisation): SCORING_ENGINE with persisted scorecards (per-dimension
  status/measurement/interval, eliminatory failures kept independent, optional weighted
  aggregate with visible formula, missing dimensions, validity controls: underpowered, wide
  interval, coverage, non-equivalent profiles, evaluator drift, overfitting signal, inconclusive
  comparison, regressions → audit event), self-contained HTML campaign report and static
  dashboard (overview/agent/campaign/finances/improvement) with inline SVG charts (ADR-0007),
  CSV exports, CLI `scorecard`, `dashboard build`, `report` now writes HTML+MD+JSON+CSV,
  `run` builds the scorecard with project weights.
- Phase 3 (measurement & economics): statistical engine (intervals, BCa bootstrap, paired /
  unpaired comparisons with INCONCLUSIVE, effect sizes, Holm, seeded sampling, variance
  decomposition, coverage property tests), TOKEN_METER (migration 0002 `usage_records`,
  attribution, Anthropic/OpenAI subset conventions, status-inheriting aggregation),
  COST_CONTROLLER (price registry import, subset-aware costing, history-based forecast,
  hierarchical budgets, atomic reservations, thresholds, 12-thread race test), orchestrator
  reservations + STOPPED_BUDGET + bounded workers, `http.json` adapter (optional `httpx`),
  report v1.1 (CIs, cost, cost per valid run, baseline comparison, non-equivalence warnings),
  CLI `compare`, `budget set|status`, `prices import|list`, `run --workers/--baseline`.
- Phase 2 (MVP): SQLite storage (migrations, transactions, artifacts, append-only audit with
  SHA-256 chain + `db check`), project/scenario loader, simulated adapters
  (`sim.deterministic`, `sim.stochastic`) and `python.callable`, eight deterministic evaluators,
  campaign orchestrator (profiles QUICK/STANDARD/DEEP/EXTENDED, DRY_RUN, seeded repetitions,
  eliminatory stop), JSON + Markdown reports, CLI `run`/`report`/`campaigns`/`scenarios
  validate`/`db *`, demo project, 86 provider-free tests.
- Phase 1: package skeleton, public contracts v1.0.0 (scenario, run, usage, pricing, cost,
  trajectory, evaluation, campaign, budget, audit, scorecard, ticket), module ports, CLI
  (`version`, `export-schemas`), documentation set, ADR-0001…0006, contract and documentation
  consistency tests.
