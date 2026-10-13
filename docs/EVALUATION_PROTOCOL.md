# Evaluation protocol

## 1. Scenario format

Canonical contract: `evalkit.contracts.Scenario` (JSON Schema `schemas/Scenario.schema.json`).
Scenarios are YAML or JSON files under `scenarios/<project>/<agent>/`, one per file, validated
by schema on load. Fields map 1:1 to the specification §3.1: stable id, project/agent,
description/objective, inputs, context/fixtures, expected behaviour, constraints, reference
outputs, sources of truth, verifications, criticality, repetitions, budget, success criteria,
dataset kind, provenance. The format carries no model-specific field.

### Development vs holdout

`dataset: DEVELOPMENT` scenarios may be used to diagnose and fix an agent.
`dataset: HOLDOUT` scenarios are protected: they are never shown to the improvement loop, their
directory is excluded from fix experiments, and a change to a HOLDOUT scenario is a
governance-level action (level 4). A result that improves only on DEVELOPMENT scenarios is
flagged as possible overfitting (`docs/SCORING.md` §4).

### Versioning

`version` is semver. Changing expectations, references or verifications bumps it; results are
always stored with the scenario version they were produced against, so historical campaigns
remain interpretable.

## 2. Verifications

Each `VerificationSpec` names a registered evaluator, a dimension, parameters, a `blocking`
flag (eliminatory) and an optional weight. Families: deterministic, schema, reference, rule,
trace, LLM-assisted, human, composite. LLM-assisted evaluators must declare a calibration set
and a version; repeated similar judgements are not treated as proof of accuracy
(`docs/METRICS.md`).

## 3. Campaign lifecycle

PLANNED → (DRY_RUN) → RUNNING → COMPLETED | STOPPED_BUDGET | STOPPED_ELIMINATORY | SUSPENDED
| FAILED. Transitions are audit events. A campaign records the price snapshot it used, the
seed, the profile, the baseline it compares to and the EVALKIT version.

## 4. Profiles

| Profile | Intent | V1 rules (explicit, simple) |
|---|---|---|
| QUICK | after a change | deterministic checks + CRITICAL/HIGH scenarios, 1 repetition |
| STANDARD | regular | all scenarios, repetitions from scenario (min 1) |
| DEEP | pre-release | all scenarios, repetitions ≥ 3 for non-deterministic adapters, holdout included |
| EXTENDED | audit | DEEP + robustness/adversarial sets, repetitions sized by the statistical protocol |

Campaign size is derived from risk, budget and the statistical protocol, never from a fixed
volume. A campaign may stop early after an established eliminatory failure, subject to audit
rules (the stop and its reason are recorded).

## 5. Progressive execution (V1)

1. Run deterministic verifications first. 2. Run the first batch. 3. Analyse. 4. Estimate
uncertainty. 5. Check budget. 6. Continue or conclude. 7. Record the stop reason.
Insufficient data ⇒ INCONCLUSIVE, never a forced verdict. Adaptive selection is V2.

## 6. Reuse of results

Cached results are reused only when scenario version, agent version, adapter version,
evaluator version and relevant configuration are identical; otherwise they are invalid.
