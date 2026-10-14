# Changelog

All notable changes to this project are documented here (Keep a Changelog, semver).

## [Unreleased]

### Added
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
