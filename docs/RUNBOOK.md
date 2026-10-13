# Runbook

Operational procedures. Sections marked (Phase N) are filled when the feature lands; until
then they state the intended procedure only and must not be relied on.

## Install
See `README.md` quick start. Production: `pip install graines-evalkit[api]` or the Docker
image (`docs/DISTRIBUTION.md`).

## Configuration
`EVALKIT_DATA_DIR` (default `./data`), `EVALKIT_CONFIG` (YAML), provider keys via
`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` or a secrets file referenced by config. (Phase 2)

## Run a campaign
`evalkit run --project <id> --agent <id> --profile STANDARD [--dry-run]`. (Phase 2)

## Backup
Stop writers, copy `data/evalkit.db` (SQLite online backup API via `evalkit db backup`),
`data/artifacts/`, `data/audit/*.jsonl`. (Phase 3)

## Restore
`evalkit db restore <backup>`; verify with `evalkit db check` (integrity + hash chain). (Phase 3)

## Resume after interruption
`evalkit campaign resume <campaign_id>`: releases stale reservations, re-plans remaining runs,
continues; all actions audited. (Phase 7)

## Scheduling without Cowork
cron / systemd timer / container `scheduler` mode with a YAML plan. (Phase 7)
