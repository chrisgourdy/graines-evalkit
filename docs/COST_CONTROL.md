# Cost control (COST_CONTROLLER)

Contracts: `Budget`, `BudgetThresholds`, `PriceEntry`, `Cost`, `CampaignPlan`,
`cost_controller.Reservation`. Enforcement is code, independent of any LLM.

## 1. Price registry

Versioned `PriceEntry` records (provider, model, validity window, per-category tariffs,
currency, source, verification date, rules). Lookup = provider + model + date. No entry ⇒
`Cost(status=UNKNOWN)`. Campaigns freeze the price ids they used so historical reports stay
interpretable. Currency conversions store the rate, source and date (`FxRate`).

## 2. Budgets

Scopes: organisation, project, agent, campaign, day, month, evaluation type. Monetary and token
caps. Inheritance: a child without a cap inherits the parent's; the tightest applicable cap
wins. There is no built-in default budget: a paid run with no applicable budget is BLOCKED.

## 3. Forecast before execution

`forecast(campaign)` estimates runs, tokens, agent cost, evaluator cost, repetition cost,
possible retry cost, external costs and the uncertainty of the forecast. Basis: historical
usage of the same agent/scenario when available, else conservative defaults (flagged).
`DRY_RUN` renders the plan and forecast without any paid call.

## 4. Reservations

Before each paid call: atomic check-and-reserve against every applicable budget, inside a
storage transaction with a lock, so concurrent workers cannot jointly exceed a cap. After the
call: settle (reserved vs observed), release the difference. Unused reservations are released
at run end and by a janitor on resume. Every decision is an audit event.

## 5. Thresholds

info → warning → blocking cap → campaign suspension → authorised resume. A blocking stop
prevents *new* calls; a call already accepted by a provider may still be billed, and some usage
is only known after the fact. EVALKIT therefore never claims absolute impossibility of overrun.

## 6. Optimisation

Trade-off between cost, coverage, reliability, criticality and uncertainty via the four
profiles (`docs/EVALUATION_PROTOCOL.md`). Critical tests are never dropped to save tokens.
Early stop after an established eliminatory failure. Adaptive optimisation: V2.
