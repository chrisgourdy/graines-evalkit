# Runbook

Operational procedures. Sections marked (Phase N) are filled when the feature lands; until
then they state the intended procedure only and must not be relied on.

## Install
See `README.md` quick start. Production: `pip install graines-evalkit[api]` or the Docker
image (`docs/DISTRIBUTION.md`).

## Configuration
`EVALKIT_DATA_DIR` (default `./data`, or `--data-dir`). A project is a directory holding
`evalkit.yaml` (project id, agents → adapter/version/params) and a `scenarios/` tree.
Provider keys (Phase 3+) come from environment variables, never from files in the repo.

## Run a campaign
`evalkit scenarios validate <project_dir>` then
`evalkit run <project_dir> --agent <id> --profile quick|standard|deep|extended [--seed N]
[--repetitions N] [--dry-run] [--stop-on-eliminatory]`. Reports land in
`<data>/reports/<campaign_id>.{json,md}`; `evalkit report <campaign_id>` regenerates them;
`evalkit campaigns --project <id>` lists campaigns.

## Budgets and prices
`evalkit prices import prices/<file>.yaml` (template: `prices/TEMPLATE.prices.yaml`; every
entry needs a source and a verification date). `evalkit budget set project <id> --max-cost X`
before any cost-bearing campaign; `evalkit budget status` shows spent = settled + open
reservations. `evalkit compare <baseline> <candidate>` runs the paired comparison.

## API
`EVALKIT_API_KEY=<secret> evalkit api serve --data-dir data --projects-dir <root>` where
`<root>/<project_id>/evalkit.yaml` exists. Loopback by default; put a TLS reverse proxy in
front before exposing it. Docker: `docker run -e EVALKIT_API_KEY=… -p 127.0.0.1:8765:8765
-v evalkit-data:/data graines/evalkit api`.

## Audit
`evalkit db check` verifies the audit hash chain and SQLite integrity;
`evalkit db export-audit out.jsonl [--campaign <id>]` exports events.

## Backup
Stop writers, copy `data/evalkit.db` (+ `-wal`/`-shm` if present, or run `evalkit db backup`
once available — Phase 3), `data/artifacts/`, `data/reports/`. (Phase 3)

## Restore
`evalkit db restore <backup>`; verify with `evalkit db check` (integrity + hash chain). (Phase 3)

## Resume after interruption
`evalkit campaign resume <campaign_id>`: releases stale reservations, re-plans remaining runs,
continues; all actions audited. (Phase 7)

## Scheduling without Cowork
cron / systemd timer / container `scheduler` mode with a YAML plan. (Phase 7)
