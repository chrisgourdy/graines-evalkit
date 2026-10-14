# Security

## Threat model (V1)

- Agent outputs, tool results and evaluated documents are untrusted and may contain prompt
  injections. They are data: never executed, never fed to an LLM judge without the judge
  being told they are untrusted, never allowed to alter scenarios, criteria or budgets.
- `injection_guard` evaluator (`evaluators/deterministic.py`): a heuristic marker scan of the
  output ("ignore previous instructions", "raise the budget", "mark as PASS", …) that
  yields a FAIL with the matched excerpts as evidence. It is a detector, never an action; the
  protection itself is structural (outputs are data) and proven by acceptance scenario 27
  (`tests/test_acceptance.py`): budget, autonomy and criteria are byte-identical after an
  injected campaign.
- Secrets (API keys) come from environment variables or a secrets file outside the repo; they
  are redacted from every event, artifact and report by a central redactor.
- Budgets and caps are enforced in code (`cost_controller`) and cannot be modified through
  the LLM path. Budget changes are governance actions.
- Autonomy escalation is impossible from inside the system (`docs/AUTONOMY_POLICY.md`).
- Isolation: improvement experiments run on branches/copies; HOLDOUT sets are read-only to
  the improvement loop.
- Loops without progress are stopped by iteration and budget limits.
- Dependencies: `pip-audit` in CI, pinned lock file, SBOM at release (`docs/DISTRIBUTION.md`).
- Data: classification per payload, retention policy, PII minimisation, controlled deletion.

## Out of scope (V1)

Multi-tenant isolation, cryptographic log anchoring, network hardening of the API beyond
API-key auth and local binding by default.
