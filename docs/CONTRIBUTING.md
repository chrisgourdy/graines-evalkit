# Contributing (humans and agents)

1. Read `CLAUDE.md`, then `docs/STATUS.md` and `docs/BACKLOG.md`.
2. Environment: `uv venv .venv --python 3.13 && uv pip install -e ".[api]" --group dev`.
3. Before any commit: `ruff check`, `ruff format --check`, `mypy`, `pytest` — all green.
4. One logical change per commit, conventional message. Update `CHANGELOG.md`, `docs/STATUS.md`
   and `CLAUDE.md` §2 when the project state changes. Add an ADR for structural decisions.
5. Never claim a capability without a test that proves it. Simulated ≠ production.
6. Never touch `scenarios/**/holdout/` from an improvement experiment.
7. Secrets never enter the repository, logs or artifacts.
8. External publication requires explicit human authorisation.
