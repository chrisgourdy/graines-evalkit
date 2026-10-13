# Statistical methods

This document is the contract of the `stats` package. Every function states its assumptions;
when they are not met, the result is flagged and the conclusion is INCONCLUSIVE.

## 1. Sources of variability (never pooled blindly)

| Source | What varies | Handling |
|---|---|---|
| Between generations | same scenario, same agent, different sampling | repetitions with distinct seeds; within-scenario dispersion |
| Between scenarios | different inputs | scenario is the primary sampling unit for campaign-level claims |
| Between environments | model version, tool state, time | recorded as covariates; cross-environment pooling is flagged |
| Between evaluators | judge variance (LLM/human) | evaluator version and calibration set recorded; inter-rater agreement when > 1 |

Observations are **not** assumed independent. Repetitions of one scenario are clustered;
campaign-level intervals use the scenario as the unit (cluster bootstrap) unless the user
explicitly asks for generation-level dispersion. A repeated identical answer is not evidence of
correctness.

## 2. Monte-Carlo (V1)

Seeded repeated execution and controlled sampling: multiple runs per scenario, representative
scenario sampling (stratified by criticality/tag), distribution estimation, dispersion,
failure-rate estimation, tail analysis (worst-k), configuration comparison, one-factor
sensitivity. All sampling is seeded and the seed is stored with the campaign.

## 3. Inference

| Quantity | Method | Assumptions / notes |
|---|---|---|
| Proportion (pass rate) | Wilson score interval (default); Clopper-Pearson for n < 10 or p near 0/1 | binomial, independent trials at the chosen unit |
| Mean (latency, score) | t-interval when n ≥ 30 and no heavy tails; else BCa bootstrap | CLT only when its conditions hold; skew and n are checked |
| Paired comparison (same scenarios, two versions) | paired bootstrap on per-scenario differences; sign test as robustness check | pairing by scenario id and version |
| Unpaired comparison | bootstrap difference of means/proportions | flagged as weaker than paired |
| Effect size | Cohen's h (proportions), Cohen's d / Cliff's delta (continuous) | reported alongside p-values, never alone |
| Variance | sample variance; between/within decomposition (one-way ANOVA-style, V1 descriptive) | — |
| Rare events | rule of three (0/n), Jeffreys interval | never a point estimate of 0 without an interval |
| Multiple comparisons | Holm correction across dimensions/scenarios in a report | correction method recorded in the result |

## 4. Interpretation rules

- Absence of a detected difference ≠ equivalence. Equivalence requires a TOST-style test with a
  declared margin (V1.1).
- INCONCLUSIVE when: n below the minimum for the method, interval spans the decision
  threshold, assumptions violated, or evaluator coverage is incomplete.
- Every reported figure carries n, method, level, and warnings.

## 5. Markov chains (V2, contracts in V1)

`Trajectory` records states, transitions, actions, tools, errors and retries. V2 will estimate
transition probabilities, absorption, loops and expected time-to-termination, after testing
the Markov property (order-1 vs order-2 likelihood comparison). The hypothesis is never assumed.

## 6. Self-evaluation

`tests/statistical/` contains seeded property tests: coverage of intervals on synthetic data
(e.g. Wilson 95 % interval covers the true p in ≈ 95 % of 10 000 simulations), bootstrap
stability, and INCONCLUSIVE triggering on under-powered data.
