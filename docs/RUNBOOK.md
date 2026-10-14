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
`evalkit db backup <dest_dir> [--no-artifacts]` — online, consistent copy through the SQLite
backup API (safe while campaigns run), plus `artifacts/` and `reports/`, plus `manifest.json`
(sizes, applied migrations, audit-chain verdict of the source). Exit code 1 when the source
chain is broken: back it up anyway, then investigate.

## Restore
Stop every writer (scheduler, API), then `evalkit db restore <backup_dir> --yes --data-dir
<data>`. The backup is refused when `PRAGMA integrity_check` fails or its audit chain is
broken; on success the data directory is replaced, migrations are applied, a
`human.intervention` event `db.restore` is appended and the chain re-verified. Exercised by
`tests/test_autonomy.py::test_backup_and_restore_keep_chain`.

## Resume after interruption
`evalkit campaign resume <campaign_id> --project-dir <proj>` for a campaign left RUNNING or
FAILED by a crash. Runs stuck RUNNING/PENDING are kept as CANCELLED (no `error`: they never
count as agent failures), unsettled reservations are released, the remaining attempts are
re-planned under new attempt numbers (every seed is recorded on its run) and the campaign
resumes to a normal end with scorecard and reports. Refused when the campaign already ended,
when the agent version in the project changed, or when scenarios disappeared. The scheduler
does this on its own at the next tick (`running_campaign_id` in `schedule_state`).

## Scheduling without Cowork
A YAML plan (`scenarios/examples/schedule.example.yaml`) declares jobs: project, agent,
profile, interval, baseline policy, optional retrofit / apply / confirm, cost cap per cycle,
loop guards. Three ways to run it:

- cron / systemd timer: `evalkit schedule run plan.yaml --once --data-dir /var/lib/evalkit`
  (one tick: due jobs run, the process exits);
- long-running: `evalkit schedule run plan.yaml --poll-seconds 300`;
- container: `docker run … graines/evalkit scheduler /projects/plan.yaml [--once]`.

One scheduler per data directory (`scheduler.lock`, stale locks of dead processes are
reclaimed). `evalkit schedule status plan.yaml` prints each job's persisted state;
`evalkit schedule resume-job plan.yaml <job> --note "…"` un-pauses a job stopped by the
failure guard (audited as `human.intervention`). What a job does per tick, in order:
resume an interrupted campaign if any, else plan + (optional campaign budget) + execute →
scorecard → healthy ⇒ becomes `last_good`; incident ⇒ retrofit only if `retrofit: true`,
a known-good baseline exists and the guards allow (max per day, cool-down) → fix applied
only if `apply_when_allowed: true` *and* the project policy grants level 3 → DEEP
confirmation → rollback when it fails. Every step is an audit event (`component=scheduler`
or `improvement`).
