# Distribution

One engine, three distributions. None is published without explicit human authorisation.

| Distribution | Artifact | Contents | Built/tested where |
|---|---|---|---|
| PyPI | `graines-evalkit` wheel + sdist | engine, CLI, contracts, storage, API; extras `api`, `http`, `anthropic`, `openai`, `otel` | `uv build`, then install in a clean venv and run the demo (CI job `wheel`) |
| Docker/OCI | `graines/evalkit` (linux/amd64, linux/arm64) | same wheel + `[api,http]`; entrypoint modes `cli` (default), `api`, `worker <project> <agent> [profile]`, `scheduler <plan.yaml> [--once]` (Phase 7, `docs/RUNBOOK.md`); non-root uid 10001; volumes `/data`, `/projects`; env `EVALKIT_DATA_DIR`, `EVALKIT_PROJECTS_DIR`, `EVALKIT_API_KEY`, `EVALKIT_API_HOST/PORT` | **CI only** (`docker` job: multi-arch build without push + amd64 smoke run); `docker/compose.demo.yml` (read-only root fs, no-new-privileges) |
| npm | `@graines/evalkit` | TypeScript fetch client (`launchCampaign`, `waitForCampaign`, results/scorecard/report/events, `pushUsage`, `pushEvent`), contract types generated per schema (`npm run gen`), usage builders for OpenAI/Anthropic payloads | `npm ci && npm run gen && npm test` (CI job `sdk`, which also fails if generated types drift from `schemas/`) |

HTTP API: `evalkit api serve` (FastAPI/uvicorn), `/v1/health` open, everything else requires
`X-EvalKit-Key` = `EVALKIT_API_KEY`; with no key configured the API answers 503 instead of
running open. Binds `127.0.0.1` unless told otherwise. Campaigns launched through the API run
in a worker thread with their own SQLite connection; clients poll `/v1/campaigns/{id}`.

The SDK never reimplements statistics or scoring; it talks to the API. Compatibility tests
run the same scenario through CLI, API and SDK and compare the persisted results.

Release pipeline (`docs/RELEASE_POLICY.md`): lint → types → tests → build wheel → build
image (CI) → SDK tests → compatibility tests → changelog check → tag → (manual) publish.
