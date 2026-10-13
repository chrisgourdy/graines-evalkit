# ADR-0001 — Modular monolith, single canonical engine

Status: accepted · 2026-10-13

## Context
The specification lists fifteen logical responsibilities and three distributions. A premature
service-per-responsibility architecture would multiply deployment surface, contracts and
failure modes before any evaluation cycle works.

## Decision
One Python package `evalkit` with one sub-package per responsibility, each exposing a port in
`interfaces.py`. CLI, API, workers and scheduler are thin entry points over the same engine.
Dependency rule: `contracts` depends on nothing; `core` may depend on everything; nothing
depends on entry points.

## Consequences
+ one codebase to test, one version, three packagings.
+ ports allow swapping storage or adapters without touching callers.
− process-level isolation (e.g. untrusted adapters) must be added explicitly when needed.
