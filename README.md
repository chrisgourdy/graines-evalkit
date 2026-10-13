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

Pre-alpha — Phase 1 (architecture) complete, Phase 2 (MVP end-to-end cycle) in progress.
See [docs/ROADMAP.md](docs/ROADMAP.md) and [CLAUDE.md](CLAUDE.md) for the current state.
Nothing in this repository is to be considered operational until the acceptance report
(`docs/ACCEPTANCE_REPORT.md`) says so, with evidence.

## Quick start (developer)

```bash
uv venv .venv --python 3.13 && source .venv/bin/activate
uv pip install -e ".[api]" --group dev
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

## License

Proprietary — Graines AI. Licensing model to be decided before any external release
(see docs/BACKLOG.md).
