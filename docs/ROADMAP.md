# Roadmap

Boundaries may move when tests or constraints justify it; the goal is a reliable product.

## Phases (method) and acceptance criteria

| Phase | Deliverable | Acceptance |
|---|---|---|
| 0 Audit | environment audit, scoping decisions | recorded (done 2026-10-13) |
| 1 Architecture | repo, CLAUDE.md, contracts, ports, docs, ADRs | ruff + mypy strict + pytest green; docs consistency test green; first commit (done) |
| 2 MVP | storage (SQLite/JSONL/artifacts), sim adapters, deterministic evaluators, orchestrator, CLI `run`, first persisted JSON/Markdown report | `evalkit run` on an example project produces a stored campaign, runs, results and a report, with tests |
| 3 Measurement & economics | stats (intervals, paired comparison, bootstrap, Monte-Carlo), TOKEN_METER, COST_CONTROLLER (registry, forecast, reservations, caps, concurrency), AUDIT_TRAIL runtime | statistical property tests; concurrent-budget test; chronology reconstruction test |
| 4 Scoring & visualisation | scorecards, validity controls, HTML report with charts, dashboard pages | report rendered from stored data only; chart library choice recorded (ADR) |
| 5 Distribution | wheel, Dockerfile + compose (CI build), npm SDK, compatibility tests, CI pipeline | wheel installs in a clean venv; image builds in CI for amd64/arm64; SDK tests pass |
| 6 Continuous improvement | backlog/tickets, incidents, retrofit cycle, learnings KB, self-evaluation | retrofit cycle demonstrated end-to-end on a simulated regression |
| 7 Autonomy | scheduler entrypoints, policies, resume/restore, loop guards | campaign runs from a cron/container with no Cowork; interrupted campaign resumes |
| 8 Acceptance | the 30 mandatory scenarios executed, acceptance report with evidence | each scenario has a pre-defined criterion and a recorded result; failures stay visible |

## V1 — usable foundations
Everything in phases 1–8 above.

## V1.1 — hardening
LLM-judge calibration, drift alerts, advanced cost analyses, incident replay, richer
dashboards, automated isolated experiments, OTLP ingestion, TOST equivalence tests.

## V2 — quality intelligence
Markov trajectory analysis, adaptive scenario selection, metamorphic tests, statistical
campaign optimisation, benchmark-contamination detection, spend forecasting, cross-project
intelligence (permission-bound), deeper governed self-improvement, evidence packs.
