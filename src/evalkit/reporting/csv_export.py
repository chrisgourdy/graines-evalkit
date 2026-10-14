"""CSV exports of a campaign: runs, results, usage records."""

from __future__ import annotations

import csv
from pathlib import Path

from evalkit.storage.sqlite import SQLiteRepository


def export_campaign_csv(repo: SQLiteRepository, campaign_id: str, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_path = out_dir / f"{campaign_id}.runs.csv"
    results_path = out_dir / f"{campaign_id}.results.csv"
    usage_path = out_dir / f"{campaign_id}.usage.csv"
    runs = list(repo.list_runs(campaign_id))
    with runs_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "run_id",
                "scenario_id",
                "scenario_version",
                "attempt",
                "seed",
                "status",
                "latency_ms",
                "cost_status",
                "cost_amount",
                "currency",
                "error",
            ]
        )
        for r in runs:
            w.writerow(
                [
                    r.run_id,
                    r.scenario_id,
                    r.scenario_version,
                    r.attempt,
                    r.seed,
                    r.status.value,
                    r.latency_ms,
                    r.cost.status.value if r.cost else "",
                    str(r.cost.amount) if r.cost and r.cost.amount is not None else "",
                    r.cost.currency if r.cost else "",
                    r.error or "",
                ]
            )
    with results_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "result_id",
                "run_id",
                "scenario_id",
                "evaluator_id",
                "evaluator_version",
                "dimension",
                "control_state",
                "status",
                "measurement",
                "score",
                "value",
                "unit",
                "blocking",
                "message",
            ]
        )
        for r in runs:
            for res in repo.list_results(r.run_id):
                w.writerow(
                    [
                        res.result_id,
                        res.run_id,
                        r.scenario_id,
                        res.evaluator_id,
                        res.evaluator_version,
                        res.dimension.value,
                        res.control_state.value,
                        res.status.value,
                        res.measurement.value,
                        res.score,
                        res.value,
                        res.unit or "",
                        int(res.blocking),
                        res.message,
                    ]
                )
    with usage_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        cols = [
            "usage_id",
            "run_id",
            "scenario_id",
            "evaluator_id",
            "provider",
            "model",
            "source",
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "cache_creation_tokens",
            "reasoning_tokens",
            "billable_total",
            "cost_status",
            "cost_amount",
            "cost_currency",
            "price_id",
        ]
        w.writerow(cols)
        for row in repo._conn.execute(
            f"SELECT {', '.join(cols)} FROM usage_records WHERE campaign_id=? ORDER BY recorded_at",  # noqa: S608
            (campaign_id,),
        ):
            w.writerow([row[c] if row[c] is not None else "" for c in cols])
    return [runs_path, results_path, usage_path]
