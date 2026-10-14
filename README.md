# EVALKIT

Evaluation, observability and continuous-improvement framework for AI agents.

EVALKIT answers three questions about any agent, whatever its model, provider, language or
architecture, as long as an adapter exists:

1. Does this agent actually work, and with what *measured* reliability?
2. What does running it cost, and what does proving its quality cost?
3. How do we prove that a change improves it without compromising reliability?

One canonical Python engine, three distributions (PyPI `graines-evalkit`, Docker
`graines/evalkit`, npm `@graines/evalkit` SDK). Built with Claude Cowork; runs without it.

## Status

Pre-alpha, V1 candidate — Phases 1 to 8 complete. Acceptance: 29 of 30 scenarios PASS on
simulated agents, 1 BLOCKED (Docker, CI only) — `docs/ACCEPTANCE_REPORT.md`. Release steps
that publish anything wait for explicit authorisation (`docs/RELEASE_CHECKLIST.md`).
See [docs/ROADMAP.md](docs/ROADMAP.md) and [CLAUDE.md](CLAUDE.md) for the current state.
Nothing in this repository is to be considered operational until the acceptance report
(`docs/ACCEPTANCE_REPORT.md`) says so, with evidence.

## Tutoriel (français)

Le guide d'utilisation complet — installation, description d'un projet et de ses scénarios,
profils de campagne, tarifs et budgets, lecture des scorecards, API et SDK, Docker, limites
actuelles — est dans **[docs/TUTORIEL.md](docs/TUTORIEL.md)**. Il reflète l'état vérifié du
projet (`docs/STATUS.md`) et est mis à jour à chaque phase.

## Quick start (developer)

```bash
uv venv .venv --python 3.13 && source .venv/bin/activate
uv pip install -e ".[api,http]" --group dev
evalkit version
pytest
```

## Layout

```
src/evalkit/          canonical engine (modular monolith, see docs/ARCHITECTURE.md)
  contracts/          versioned public data contracts (pydantic) → JSON Schema → TS SDK
  core/ adapters/ evaluators/ stats/ trajectory/ token_meter/ cost_controller/
  scoring/ reporting/ audit/ feedback/ improvement/ scheduler/ governance/ storage/ cli/
scenarios/            scenario files (DEVELOPMENT and protected HOLDOUT sets)
docs/                 canonical documentation and ADRs
tests/                unit, integration, statistical, documentation-consistency tests
sdk/typescript/       npm SDK (Phase 5)
```

## Documentation

Start at [CLAUDE.md](CLAUDE.md) — the index every contributor (human or agent) reads first.
Users start at [docs/TUTORIEL.md](docs/TUTORIEL.md) (in French).

## License

Proprietary — Graines AI. Licensing model to be decided before any external release
(see docs/BACKLOG.md).
