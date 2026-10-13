# ADR-0003 — Usage and cost provenance statuses

Status: accepted · 2026-10-13

## Context
Token figures come from providers, estimators or nowhere; tariffs may be unknown; sub-categories
may already be included in totals. Silent mixing produces wrong invoices and false comparisons.

## Decision
`TokenUsage.source ∈ {REPORTED, ESTIMATED, UNKNOWN}` with mandatory `estimation_method` for
ESTIMATED and no figures for UNKNOWN; `TokenUsage.subsets` declares inclusion relations used by
`billable_total()`; `Cost.status ∈ {MEASURED, ESTIMATED, UNKNOWN}` with `price_id` traceability;
aggregates inherit the weakest status of their members.

## Consequences
+ reports can never show an estimate as a measurement.
− provider conventions must be catalogued and tested against real payloads (EK-0007).
