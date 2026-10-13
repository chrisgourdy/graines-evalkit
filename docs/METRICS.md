# Metrics

Each dimension (`contracts.Dimension`) has a definition, a computation and documented limits.
A metric that cannot be measured is `NOT_EVALUATED` / `UNAVAILABLE`, never a made-up number.

| Dimension | Definition | Computation (V1) | Measurement | Limits |
|---|---|---|---|---|
| accuracy | Output matches reference | exact/normalised match, numeric tolerance, set overlap, reference lookup | OBJECTIVE | needs references; free text needs LLM/human judge |
| compliance | Mandatory constraints respected | rule evaluators (regex, forbidden content, policy checks) | OBJECTIVE | rules must be explicit |
| completeness | Required elements present | checklist / required-keys evaluator | OBJECTIVE or LLM_JUDGED | checklist must be versioned |
| consistency | Same input → same conclusion across repetitions | agreement rate across repetitions (normalised output) | STATISTICAL | agreement ≠ correctness |
| format | Output structure valid | JSON Schema / type / shape evaluator | OBJECTIVE | — |
| constraints | Length, language, forbidden tools, time limits | deterministic checks | OBJECTIVE | — |
| decision_reliability | Decision variable correct and stable | accuracy of the decision field × consistency | STATISTICAL | requires labelled decisions |
| tool_use | Right tools, right args, no forbidden calls | trace evaluator over `Trajectory` | OBJECTIVE | needs trajectory reporting |
| stability | Low dispersion of scores/latency across repetitions | coefficient of variation, failure-rate CI | STATISTICAL | n ≥ 3 |
| robustness | Behaviour under perturbed inputs | paired comparison original vs perturbed (metamorphic, V1.1) | STATISTICAL | perturbations must declare expected invariants |
| security | No injection follow-through, no secret leakage | rule + trace evaluators on adversarial scenarios | OBJECTIVE | coverage limited to known attacks |
| latency | Wall-clock per run | measured by core; mean/p50/p95 with CI | OBJECTIVE | environment-dependent |
| tokens | Consumption per run/scenario | TOKEN_METER aggregation (REPORTED preferred) | OBJECTIVE or ESTIMATED | ESTIMATED is flagged |
| cost | Monetary cost per run / per valid answer | price registry × usage | OBJECTIVE or ESTIMATED/UNKNOWN | unknown tariff ⇒ UNKNOWN |
| business | Domain KPI defined by project | project-specific evaluator | any | must be declared per project |

"Valid answer" for cost-per-valid-answer: a run whose blocking verifications all PASS and
whose non-blocking verifications have no FAIL (definition recorded in each report).

LLM-assisted judgements are `LLM_JUDGED`, carry the judge model, prompt version and calibration
set id, and their cost is metered separately from the agent's.
