# Autonomy policy

Levels (`contracts.AutonomyLevel`), enforced by `governance.PolicyEngine`:

| Level | Allowed without a human | Examples |
|---|---|---|
| 1 Automatic | tests, statistics, collection, reporting, ticket creation, analyses | run STANDARD campaign, open ticket |
| 2 Isolated automatic | proposals, branches, experiments, tests and comparisons in isolation | propose a prompt fix, run it on a branch against DEVELOPMENT set |
| 3 Controlled apply | low-risk fixes in approved perimeters, with tests and rollback | apply a config change marked low-risk by project policy |
| 4 Human validation | critical changes, sensitive production, evaluation rules, permissions, destructive actions, external publication | change success criteria, publish package, delete data |

## Enforcement (`governance/policy.py`)

`ProjectPolicyEngine.decide(action)` computes `required = max(action.required_level,
LEVEL_OF_KIND[kind])` — a caller can never lower the level of a kind — then refuses when:
the actor starts with `agent:` and `required > 2` (agents never apply, whatever the project
says); the kind is in `ALWAYS_HUMAN` (`change_success_criteria`, `change_holdout`,
`change_permissions`, `change_budget`, `publish_external`, `delete_data`,
`apply_fix_production`) or unknown → level 4; `required > autonomy.max_level`; level 3 and
the kind is not in `autonomy.apply_perimeter`. Every refusal carries `requires_human=True`
and a reason; the retrofit cycle records it as the ticket decision
`HUMAN_VALIDATION_REQUIRED`. Project configuration:

```yaml
autonomy:
  max_level: 2              # default; 3 opens controlled apply, 4 is never granted by config
  apply_perimeter: []       # kinds allowed at level 3, e.g. [apply_fix_low_risk]
```

Even with `APPLY_ALLOWED`, EVALKIT does not yet write a fix into a real project (EK-0033):
the decision is recorded and the human applies it, then runs `evalkit retrofit confirm`.

Invariants: an agent cannot raise its level; cannot change the criteria it is judged on;
budgets are code-enforced; every decision is an audit event; interrupted work resumes from
persisted state; restore procedures exist (`docs/RUNBOOK.md`). Project-level policy files
declare the approved perimeters for level 3.
