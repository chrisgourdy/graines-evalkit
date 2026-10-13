# ADR-0006 — Budgets, autonomy levels and criteria changes are enforced in code

Status: accepted · 2026-10-13

## Context
An LLM-driven improvement loop could, by instruction or by injection, relax its own criteria,
raise its permissions or exceed budgets.

## Decision
`cost_controller` performs atomic check-and-reserve in storage transactions; `governance.
PolicyEngine` is consulted by `core` for every action with a required level; success-criteria
and HOLDOUT changes are level-4 actions; no code path lets an actor of kind `agent:*` modify
budgets, levels or criteria. Agent outputs are typed as untrusted data in contracts.

## Consequences
+ safety does not depend on prompt wording.
− some automation needs explicit project policy files to be allowed at level 3.
