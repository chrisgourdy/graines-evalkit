# ADR-0002 — Persistence: SQLite + JSONL + content-addressed artifacts

Status: accepted · 2026-10-13

## Context
V1 must run locally, in a container and under cron with no external service, with
transactions, migrations and append-only audit guarantees.

## Decision
SQLite in WAL mode behind the `Repository` port; numbered SQL migrations; audit table
append-only in code (no update/delete statements), per-event SHA-256 and chained hash for
tamper evidence; JSONL exports for interchange; artifacts stored by content hash under
`data/artifacts/` and referenced by `payload_ref`.

## Consequences
+ zero infrastructure, easy backup (file copy / online backup API).
+ port allows Postgres later without changing callers.
− single-writer limits: concurrency handled by SQLite locking and short transactions;
  reservations use `BEGIN IMMEDIATE`.
− no cryptographic immutability claimed (no external anchoring).
