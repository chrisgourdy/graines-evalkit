# Autonomy policy

Levels (`contracts.AutonomyLevel`), enforced by `governance.PolicyEngine`:

| Level | Allowed without a human | Examples |
|---|---|---|
| 1 Automatic | tests, statistics, collection, reporting, ticket creation, analyses | run STANDARD campaign, open ticket |
| 2 Isolated automatic | proposals, branches, experiments, tests and comparisons in isolation | propose a prompt fix, run it on a branch against DEVELOPMENT set |
| 3 Controlled apply | low-risk fixes in approved perimeters, with tests and rollback | apply a config change marked low-risk by project policy |
| 4 Human validation | critical changes, sensitive production, evaluation rules, permissions, destructive actions, external publication | change success criteria, publish package, delete data |

Invariants: an agent cannot raise its level; cannot change the criteria it is judged on;
budgets are code-enforced; every decision is an audit event; interrupted work resumes from
persisted state; restore procedures exist (`docs/RUNBOOK.md`). Project-level policy files
declare the approved perimeters for level 3.
