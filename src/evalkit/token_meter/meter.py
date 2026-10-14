"""SQLite token meter: one row per usage record with full attribution; aggregation that
never sums an UNKNOWN record as zero and inherits the weakest source status."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from evalkit.contracts import Cost, TokenUsage, UsageSource, new_id, utcnow
from evalkit.storage.sqlite import SQLiteRepository
from evalkit.token_meter.interfaces import UsageAttribution

_CATEGORIES = (
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "cache_creation_tokens",
    "reasoning_tokens",
)
_FILTERS = {
    "organization_id",
    "project_id",
    "agent_id",
    "agent_version",
    "campaign_id",
    "scenario_id",
    "run_id",
    "evaluator_id",
    "provider",
    "model",
    "period",
}


class SQLiteTokenMeter:
    def __init__(self, repo: SQLiteRepository) -> None:
        self.repo = repo

    def record(
        self, usage: TokenUsage, attribution: UsageAttribution, cost: Cost | None = None
    ) -> str:
        usage_id = new_id("usg")
        period = attribution.period or date.today().isoformat()
        self.repo._conn.execute(
            "INSERT INTO usage_records(usage_id, recorded_at, organization_id, project_id,"
            " agent_id, agent_version, campaign_id, scenario_id, run_id, step_index, call_id,"
            " evaluator_id, period, provider, model, source, input_tokens, output_tokens,"
            " cached_input_tokens, cache_creation_tokens, reasoning_tokens, billable_total,"
            " cost_status, cost_amount, cost_currency, price_id, json)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                usage_id,
                utcnow().isoformat(),
                attribution.organization_id,
                attribution.project_id,
                attribution.agent_id,
                attribution.agent_version,
                attribution.campaign_id,
                attribution.scenario_id,
                attribution.run_id,
                attribution.step_index,
                attribution.call_id,
                attribution.evaluator_id,
                period,
                usage.provider,
                usage.model,
                usage.source.value,
                usage.input_tokens,
                usage.output_tokens,
                usage.cached_input_tokens,
                usage.cache_creation_tokens,
                usage.reasoning_tokens,
                usage.billable_total(),
                cost.status.value if cost else None,
                str(cost.amount) if cost and cost.amount is not None else None,
                cost.currency if cost else None,
                cost.price_id if cost else None,
                json.dumps(
                    {
                        "usage": usage.model_dump(mode="json"),
                        "cost": cost.model_dump(mode="json") if cost else None,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        return usage_id

    def aggregate(self, **filters: str) -> dict[str, Any]:
        """Totals over matching records.

        ``status`` is REPORTED only if every record is REPORTED; ESTIMATED if any is
        ESTIMATED and none UNKNOWN; PARTIAL/UNKNOWN when UNKNOWN records exist (their
        tokens are not summed, they are counted in ``records.unknown``).
        """
        clauses = [f"{k}=?" for k in filters if k in _FILTERS]
        params = [v for k, v in filters.items() if k in _FILTERS]
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.repo._conn.execute(
            f"SELECT source, input_tokens, output_tokens, cached_input_tokens,"  # noqa: S608
            f" cache_creation_tokens, reasoning_tokens, billable_total, cost_status, cost_amount,"
            f" cost_currency FROM usage_records{where}",
            params,
        ).fetchall()
        totals: dict[str, int] = dict.fromkeys((*_CATEGORIES, "billable_total"), 0)
        counts = {"reported": 0, "estimated": 0, "unknown": 0}
        cost_total = 0.0
        cost_unknown = 0
        cost_estimated = 0
        currency: str | None = None
        for r in rows:
            src = UsageSource(r["source"])
            if src is UsageSource.UNKNOWN:
                counts["unknown"] += 1
            else:
                counts["reported" if src is UsageSource.REPORTED else "estimated"] += 1
                for c in (*_CATEGORIES, "billable_total"):
                    if r[c] is not None:
                        totals[c] += int(r[c])
            if r["cost_status"] in ("MEASURED", "ESTIMATED") and r["cost_amount"] is not None:
                cost_total += float(r["cost_amount"])
                currency = currency or r["cost_currency"]
                if r["cost_status"] == "ESTIMATED":
                    cost_estimated += 1
            else:
                cost_unknown += 1
        if counts["unknown"] and (counts["reported"] or counts["estimated"]):
            status = "PARTIAL"
        elif counts["unknown"]:
            status = "UNKNOWN"
        elif counts["estimated"]:
            status = "ESTIMATED"
        else:
            status = "REPORTED"
        if not rows:
            status = "NO_DATA"
        cost_status = (
            "NO_DATA"
            if not rows
            else "UNKNOWN"
            if cost_unknown == len(rows)
            else "PARTIAL"
            if cost_unknown
            else "ESTIMATED"
            if cost_estimated
            else "MEASURED"
        )
        return {
            "status": status,
            "records": counts | {"total": len(rows)},
            "tokens": totals,
            "cost": {
                "status": cost_status,
                "known_amount": cost_total,
                "currency": currency,
                "records_unknown": cost_unknown,
            },
        }

    def per_run_history(self, project_id: str, agent_id: str, limit: int = 200) -> list[int]:
        """Billable totals per run for the agent (any version) — forecast input."""
        rows = self.repo._conn.execute(
            "SELECT run_id, SUM(billable_total) AS t FROM usage_records"
            " WHERE project_id=? AND agent_id=? AND run_id IS NOT NULL AND evaluator_id IS NULL"
            " AND source<>'UNKNOWN' GROUP BY run_id ORDER BY MAX(recorded_at) DESC LIMIT ?",
            (project_id, agent_id, limit),
        ).fetchall()
        return [int(r["t"]) for r in rows if r["t"] is not None]
