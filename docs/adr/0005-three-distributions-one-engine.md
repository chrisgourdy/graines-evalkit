# ADR-0005 — Three distributions, one engine; TS SDK is a client

Status: accepted · 2026-10-13

## Context
PyPI, Docker and npm are required. Reimplementing statistics in TypeScript would create a
second source of truth.

## Decision
PyPI `graines-evalkit` is the engine. The OCI image installs that wheel and exposes CLI/API/
worker/scheduler modes. npm `@graines/evalkit` contains an API client, helpers to push events
and traces, and types generated from the JSON Schemas exported by `evalkit export-schemas`.
Compatibility tests run the same scenario through the three paths. Names chosen because
`evalkit` is taken on both registries.

## Consequences
+ one implementation of every rule.
− JS agents need a reachable API (or the CLI) to be evaluated; no offline JS engine.
