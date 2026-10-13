# Scoring (SCORING_ENGINE)

Contract: `Scorecard`, `DimensionScore`.

## 1. Principles

Each dimension is scored separately. A blocking (eliminatory) FAIL makes the overall status
FAIL whatever the other dimensions say and is listed by scenario/evaluator id. Weights are
per-project, versioned configuration; an aggregate score is computed only when the project
configuration asks for it, and then the formula, weights, exclusions and missing data are
printed next to it. Unknown is never 0 nor PASS: `NOT_EVALUATED` dimensions are listed in
`missing_dimensions` and excluded from aggregates with an explicit note.

Measurement kinds (OBJECTIVE, STATISTICAL, LLM_JUDGED, HUMAN, UNAVAILABLE) are preserved per
dimension so a reader can tell a measured fact from a judged one.

## 2. Overall status

| Condition | Status |
|---|---|
| any blocking FAIL | FAIL |
| any required dimension NOT_EVALUATED or INCONCLUSIVE | INCONCLUSIVE |
| any dimension FAIL (non-blocking) | FAIL |
| any WARNING | WARNING |
| otherwise | PASS |

## 3. Scorecard content

Version, overall status, dimensions with pass rate / mean score / CI / n, critical failures,
uncertainty, stability, cost (with status), latency, trends, baseline comparison, regressions,
campaign history, validity warnings.

## 4. Validity controls (V1 rules)

| Risk | Detection |
|---|---|
| misleading metric | dimension with n < minimum or CI wider than 0.5 → warning |
| insufficient coverage | < X % of scenarios of a criticality level executed → warning |
| overfitting to tests | improvement on DEVELOPMENT set not reproduced on HOLDOUT → warning |
| evaluator drift | LLM judge version or calibration set changed between compared campaigns → warning |
| non-equivalent comparison | different scenario versions, adapter versions or profiles → comparison refused or flagged |
| inconclusive difference | comparison CI spans 0 → INCONCLUSIVE, never "no regression" |

Control execution state and evaluation conclusion are always shown separately.
