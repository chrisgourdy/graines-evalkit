# ADR-0004 — INCONCLUSIVE and NOT_EVALUATED are first-class outcomes

Status: accepted · 2026-10-13

## Context
Forcing PASS/FAIL on under-powered data, or treating unknown as zero, produces confident wrong
decisions — the worst failure mode for a quality tool.

## Decision
`EvalStatus` includes INCONCLUSIVE and NOT_EVALUATED; `ControlState` is recorded separately
from the conclusion; `MeasurementKind.UNAVAILABLE` cannot carry a score (validated in the
contract); statistical comparisons return INCONCLUSIVE when assumptions or power are lacking;
scorecards list missing dimensions explicitly and exclude them from any aggregate.

## Consequences
+ every verdict is defensible.
− users must accept "we do not know yet" as a legitimate campaign result.
