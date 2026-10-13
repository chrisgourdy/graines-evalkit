# Acceptance scenarios (mandatory, criteria defined before execution)

Executed in Phase 8; results go to `docs/ACCEPTANCE_REPORT.md` with evidence (ids, logs,
report paths). Failures stay visible. Simulated runs are labelled as such.

| # | Scenario | Pre-defined success criterion | Needs provider |
|---|---|---|---|
| 1 | Compliant agent | all verifications PASS, scorecard PASS | no (sim) |
| 2 | Incorrect agent | reference evaluator FAIL, scorecard FAIL, ticket opened | no |
| 3 | Regression between versions | paired comparison conclusion FAIL with CI excluding 0 | no |
| 4 | Hallucination detected by reference | reference lookup FAIL with evidence diff | no |
| 5 | Result variability | stochastic adapter: dispersion and consistency metrics reported with n and CI | no |
| 6 | Monte-Carlo sampling | seeded repeated runs reproducible; distribution stored | no |
| 7 | Statistical comparison | two versions compared; method, effect size, p, CI recorded | no |
| 8 | Inconclusive result | under-powered comparison returns INCONCLUSIVE, never PASS/FAIL | no |
| 9 | Multi-step trajectory capture | steps with tools, retry, error, terminal state stored | no |
| 10 | Exact accounting of reported tokens | sum of REPORTED usage equals fixture totals, no double count | no |
| 11 | Flagged token estimation | adapter without usage → ESTIMATED with method shown in report | no |
| 12 | Cost from versioned tariff | cost equals usage × frozen price; price_id recorded; unknown model → UNKNOWN | no |
| 13 | Campaign stopped on budget | cap reached → no new call, status STOPPED_BUDGET, events logged | no |
| 14 | Concurrent budget handling | N workers cannot jointly exceed cap (test with threads/processes) | no |
| 15 | Logging and chronology reconstruction | full timeline rebuilt from events; hash chain valid | no |
| 16 | Multidimensional scorecard | per-dimension statuses, eliminatory failures independent of aggregate | no |
| 17 | Visual HTML report | HTML with charts generated from stored data, no LLM | no |
| 18 | Incident detection | failure pattern → incident event | no |
| 19 | Ticket creation | structured ticket with evidence refs | no |
| 20 | Retrofit cycle | OBSERVE→…→LEARN executed on a simulated regression, each step audited | no |
| 21 | EVALKIT self-evaluation | self-checks (stats coverage, accounting, budgets, logging) produce a scorecard | no |
| 22 | Python package install | wheel installs in a clean venv; `evalkit version` works | no |
| 23 | Docker execution | image runs `evalkit run` on the demo (CI) | no (CI) |
| 24 | npm integration | SDK launches a campaign via API and reads results | no |
| 25 | Two distinct projects | isolation of data and budgets verified | no |
| 26 | Resume after interruption | killed campaign resumes, reservations released, no duplicate runs | no |
| 27 | Prompt-injection protection | injected output does not alter criteria/budget; flagged by security evaluator | no |
| 28 | Test without external provider | full default test suite passes offline | no |
| 29 | Documentation inconsistency detection | removing a referenced doc fails the consistency test | no |
| 30 | Acceptance report with evidence | report lists each scenario, criterion, result, evidence | no |
