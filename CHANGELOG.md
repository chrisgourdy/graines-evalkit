# Changelog

All notable changes to this project are documented here (Keep a Changelog, semver).

## [Unreleased]

### Added
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
