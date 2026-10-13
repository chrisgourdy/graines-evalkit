# Observability (AUDIT_TRAIL)

Contract: `AuditEvent`, `EventType`. Port: `audit.AuditTrail`.

## 1. Events

All significant events of specification §7.1 have an `EventType`. Each event carries the
applicable metadata of §7.2 (`event_id`, UTC timestamp, type, severity, actor, project/agent/
campaign/run ids, trace/span ids, component, version, status, duration, usage, cost,
payload reference, correlation id). Absent data is `None`, explicitly.

## 2. Persistence

SQLite table `audit_events` (append-only; no UPDATE/DELETE statements exist in the code path;
a store-assigned monotonic `sequence` allows chronological reconstruction), JSONL export for
interchange, artifact files for payloads. Corrections are new events with `corrects=<id>`.
Integrity: per-event SHA-256 over the canonical JSON and a chained hash column, giving
tamper-evidence (not cryptographic immutability — no external anchoring is claimed).
Backup/restore: `docs/RUNBOOK.md`.

## 3. Security of logs

Secrets redacted at emission (`governance`/`security` redactor), data classification per
payload, retention policy per class, access control at the storage/API level, PII minimisation,
references instead of inline content, encryption at rest when the deployment requires it,
controlled deletion through retention jobs that themselves emit events. Full prompts/responses
are retained only under an explicit project policy; logs remain useful without them.

## 4. OpenTelemetry

`audit.otel` (Phase 3, optional dependency `otel`) exports events as spans/events with GenAI
semantic-convention attributes (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.*`,
`gen_ai.operation.name`) and can ingest OTLP traces from instrumented agents as trajectories.
