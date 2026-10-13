# Distribution

One engine, three distributions. None is published without explicit human authorisation.

| Distribution | Artifact | Contents | Built/tested where |
|---|---|---|---|
| PyPI | `graines-evalkit` wheel + sdist | engine, CLI, contracts, storage; extras `api`, `anthropic`, `openai`, `otel` | locally (`uv build`) and CI |
| Docker/OCI | `graines/evalkit` (linux/amd64, linux/arm64) | same wheel; modes `cli`, `api`, `worker`, `scheduler`; non-root; volumes for data; env/file config | **CI only** (no daemon in dev env); `docker/compose.demo.yml` |
| npm | `@graines/evalkit` | TypeScript API client, typed contracts generated from JSON Schemas, event/trace upload helpers, JS agent integration | locally (`npm test`) and CI |

The SDK never reimplements statistics or scoring; it talks to the API. Compatibility tests
run the same scenario through CLI, API and SDK and compare the persisted results.

Release pipeline (`docs/RELEASE_POLICY.md`): lint → types → tests → build wheel → build
image (CI) → SDK tests → compatibility tests → changelog check → tag → (manual) publish.
