"""COST_CONTROLLER runtime: budgets, forecast, atomic reservations, thresholds.

Enforcement is code: ``reserve`` runs a ``BEGIN IMMEDIATE`` transaction so that concurrent
workers (threads or processes with their own connections) cannot jointly exceed a cap. An
accepted provider call may still bill after a block; this module never claims otherwise.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Any

from evalkit import __version__
from evalkit.audit.events import make_event
from evalkit.contracts import (
    Budget,
    BudgetScope,
    Campaign,
    CampaignPlan,
    Cost,
    EventType,
    Severity,
    new_id,
    utcnow,
)
from evalkit.cost_controller.interfaces import BudgetDecision, Reservation
from evalkit.storage.sqlite import SQLiteRepository

CONSERVATIVE_TOKENS_PER_RUN = 4000
"""Used when no history exists; flagged as 'conservative_default' in the plan."""


class SQLiteCostController:
    def __init__(self, repo: SQLiteRepository, *, actor: str = "system") -> None:
        self.repo = repo
        self.actor = actor

    # ------------------------------------------------------------------ budgets
    def save_budget(self, budget: Budget) -> None:
        self.repo._conn.execute(
            "INSERT OR REPLACE INTO budgets(budget_id, scope, scope_ref, currency, max_cost,"
            " max_tokens, json) VALUES (?,?,?,?,?,?,?)",
            (
                budget.budget_id,
                budget.scope.value,
                budget.scope_ref,
                budget.currency,
                budget.max_cost,
                budget.max_tokens,
                budget.model_dump_json(),
            ),
        )
        self.repo.emit(
            make_event(
                EventType.CONFIG_CHANGED,
                component="cost_controller",
                actor=self.actor,
                payload={"budget": budget.model_dump(mode="json")},
            )
        )

    def applicable_budgets(self, campaign: Campaign, on: date | None = None) -> list[Budget]:
        """Hierarchy: campaign, agent, project, organization, day, month — all that match apply;
        the tightest cap wins because every one is checked."""
        today = on or utcnow().date()
        refs = [
            (BudgetScope.CAMPAIGN, campaign.campaign_id),
            (BudgetScope.AGENT, f"{campaign.project_id}/{campaign.agent_id}"),
            (BudgetScope.PROJECT, campaign.project_id),
            (BudgetScope.ORGANIZATION, "*"),
            (BudgetScope.DAY, today.isoformat()),
            (BudgetScope.MONTH, today.strftime("%Y-%m")),
            (BudgetScope.EVALUATION_TYPE, campaign.profile.value),
        ]
        out: list[Budget] = []
        for scope, ref in refs:
            row = self.repo._conn.execute(
                "SELECT json FROM budgets WHERE scope=? AND scope_ref=?", (scope.value, ref)
            ).fetchone()
            if row:
                out.append(Budget.model_validate_json(row["json"]))
        return out

    def spent(self, budget_id: str) -> tuple[float, int]:
        """(cost, tokens) = settled observed + open reservations (released ones excluded)."""
        row = self.repo._conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN settled=1 THEN observed_cost ELSE reserved_cost END),0)"
            " AS c, COALESCE(SUM(CASE WHEN settled=1 THEN observed_tokens"
            " ELSE reserved_tokens END),0)"
            " AS t FROM reservations WHERE budget_id=? AND released=0",
            (budget_id,),
        ).fetchone()
        return float(row["c"]), int(row["t"])

    # ----------------------------------------------------------------- forecast
    def forecast(
        self,
        campaign: Campaign | None,
        *,
        planned_runs: int,
        cost_bearing: bool,
        history_tokens: list[int] | None = None,
        price_per_million_hint: float | None = None,
        evaluator_runs_cost_bearing: int = 0,
    ) -> CampaignPlan:
        if not cost_bearing:
            return CampaignPlan(
                planned_runs=planned_runs,
                expected_tokens=None,
                expected_agent_cost=0.0,
                expected_evaluator_cost=0.0,
                expected_retry_cost=0.0,
                uncertainty="non-cost-bearing adapter: cost is 0 by construction; tokens unknown",
                basis="conservative_default",
            )
        if history_tokens:
            median = statistics.median(history_tokens)
            p90 = sorted(history_tokens)[
                min(len(history_tokens) - 1, int(0.9 * len(history_tokens)))
            ]
            per_run = int(p90)
            basis = "historical"
            uncertainty = (
                f"based on {len(history_tokens)} past runs (median {median:.0f}, p90 {p90} tokens);"
                " uses p90 per run"
            )
        else:
            per_run = CONSERVATIVE_TOKENS_PER_RUN
            basis = "conservative_default"
            uncertainty = (
                f"no history: {CONSERVATIVE_TOKENS_PER_RUN} tokens/run assumed, high uncertainty"
            )
        tokens = per_run * planned_runs
        cost = (tokens / 1_000_000 * price_per_million_hint) if price_per_million_hint else None
        if cost is None:
            uncertainty += "; no tariff hint: cost unknown"
        retry = cost * 0.1 if cost is not None else None
        return CampaignPlan(
            planned_runs=planned_runs,
            expected_tokens=tokens,
            expected_agent_cost=cost,
            expected_evaluator_cost=0.0 if evaluator_runs_cost_bearing == 0 else None,
            expected_retry_cost=retry,
            uncertainty=uncertainty + "; retry allowance 10 %",
            basis=basis,
        )

    # -------------------------------------------------------------- reservations
    def reserve(
        self,
        campaign: Campaign,
        *,
        run_id: str | None,
        expected_cost: float,
        expected_tokens: int | None,
    ) -> tuple[BudgetDecision, Reservation | None]:
        budgets = self.applicable_budgets(campaign)
        if not budgets:
            self._emit(
                EventType.BUDGET_BLOCKED,
                campaign,
                run_id,
                Severity.ERROR,
                {"reason": "no applicable budget: paid runs need an explicit budget"},
            )
            return BudgetDecision.BLOCK, None
        decision = BudgetDecision.ALLOW
        reservation_id = new_id("rsv")
        with self.repo.transaction():  # BEGIN IMMEDIATE → single writer across connections
            for b in budgets:
                cost_spent, tokens_spent = self.spent(b.budget_id)
                if b.max_cost is not None and cost_spent + expected_cost > b.max_cost:
                    self._emit(
                        EventType.BUDGET_BLOCKED,
                        campaign,
                        run_id,
                        Severity.ERROR,
                        {
                            "budget_id": b.budget_id,
                            "scope": b.scope.value,
                            "spent": cost_spent,
                            "requested": expected_cost,
                            "max_cost": b.max_cost,
                        },
                    )
                    return BudgetDecision.BLOCK, None
                if (
                    b.max_tokens is not None
                    and expected_tokens is not None
                    and tokens_spent + expected_tokens > b.max_tokens
                ):
                    self._emit(
                        EventType.BUDGET_BLOCKED,
                        campaign,
                        run_id,
                        Severity.ERROR,
                        {
                            "budget_id": b.budget_id,
                            "spent_tokens": tokens_spent,
                            "requested_tokens": expected_tokens,
                            "max_tokens": b.max_tokens,
                        },
                    )
                    return BudgetDecision.BLOCK, None
                if b.max_cost is not None:
                    ratio = (cost_spent + expected_cost) / b.max_cost
                    if ratio >= b.thresholds.warning:
                        decision = BudgetDecision.ALLOW_WITH_WARNING
                        self._emit(
                            EventType.BUDGET_THRESHOLD,
                            campaign,
                            run_id,
                            Severity.WARNING,
                            {"budget_id": b.budget_id, "level": "warning", "ratio": ratio},
                        )
                    elif ratio >= b.thresholds.info:
                        self._emit(
                            EventType.BUDGET_THRESHOLD,
                            campaign,
                            run_id,
                            Severity.INFO,
                            {"budget_id": b.budget_id, "level": "info", "ratio": ratio},
                        )
            now = utcnow().isoformat()
            for b in budgets:
                self.repo._conn.execute(
                    "INSERT INTO reservations(reservation_id, budget_id, campaign_id, run_id,"
                    " created_at, reserved_cost, reserved_tokens) VALUES (?,?,?,?,?,?,?)",
                    (
                        reservation_id,
                        b.budget_id,
                        campaign.campaign_id,
                        run_id,
                        now,
                        expected_cost,
                        expected_tokens,
                    ),
                )
        reservation = Reservation(
            reservation_id=reservation_id,
            budget_id=",".join(b.budget_id for b in budgets),
            campaign_id=campaign.campaign_id,
            run_id=run_id,
            reserved_cost=expected_cost,
            reserved_tokens=expected_tokens,
            currency=budgets[0].currency,
            created_at=utcnow(),
        )
        self._emit(
            EventType.BUDGET_RESERVED,
            campaign,
            run_id,
            Severity.INFO,
            {
                "reservation_id": reservation_id,
                "cost": expected_cost,
                "tokens": expected_tokens,
                "decision": decision.value,
            },
        )
        return decision, reservation

    def settle(
        self, reservation_id: str, observed: Cost, observed_tokens: int | None = None
    ) -> None:
        amount = float(observed.amount) if observed.amount is not None else None
        with self.repo.transaction():
            if amount is None:
                # Unknown observed cost: keep the reservation as the best estimate (conservative).
                self.repo._conn.execute(
                    "UPDATE reservations SET settled=1, observed_cost=reserved_cost,"
                    " observed_tokens=COALESCE(?, reserved_tokens) WHERE reservation_id=?",
                    (observed_tokens, reservation_id),
                )
            else:
                self.repo._conn.execute(
                    "UPDATE reservations SET settled=1, observed_cost=?, observed_tokens=?"
                    " WHERE reservation_id=?",
                    (amount, observed_tokens, reservation_id),
                )
            row = self.repo._conn.execute(
                "SELECT campaign_id, run_id FROM reservations WHERE reservation_id=? LIMIT 1",
                (reservation_id,),
            ).fetchone()
        if row:
            self.repo.emit(
                make_event(
                    EventType.BUDGET_SETTLED,
                    component="cost_controller",
                    actor=self.actor,
                    campaign_id=row["campaign_id"],
                    run_id=row["run_id"],
                    cost=observed,
                    payload={
                        "reservation_id": reservation_id,
                        "observed_known": amount is not None,
                    },
                )
            )

    def release(self, reservation_id: str) -> None:
        with self.repo.transaction():
            self.repo._conn.execute(
                "UPDATE reservations SET released=1 WHERE reservation_id=? AND settled=0",
                (reservation_id,),
            )
            row = self.repo._conn.execute(
                "SELECT campaign_id, run_id FROM reservations WHERE reservation_id=? LIMIT 1",
                (reservation_id,),
            ).fetchone()
        self.repo.emit(
            make_event(
                EventType.BUDGET_RELEASED,
                component="cost_controller",
                actor=self.actor,
                campaign_id=row["campaign_id"] if row else None,
                run_id=row["run_id"] if row else None,
                payload={"reservation_id": reservation_id},
            )
        )

    def release_stale(self, campaign_id: str) -> int:
        """Release every unsettled reservation of a campaign (resume / janitor)."""
        with self.repo.transaction():
            cur = self.repo._conn.execute(
                "UPDATE reservations SET released=1"
                " WHERE campaign_id=? AND settled=0 AND released=0",
                (campaign_id,),
            )
        return int(cur.rowcount)

    # -------------------------------------------------------------------- misc
    def _emit(
        self,
        event_type: EventType,
        campaign: Campaign,
        run_id: str | None,
        severity: Severity,
        payload: dict[str, Any],
    ) -> None:
        self.repo.emit(
            make_event(
                event_type,
                component="cost_controller",
                actor=self.actor,
                severity=severity,
                payload={**payload, "evalkit": __version__},
                project_id=campaign.project_id,
                agent_id=campaign.agent_id,
                campaign_id=campaign.campaign_id,
                run_id=run_id,
            )
        )
