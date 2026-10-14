"""Campaign report (Phase 3): JSON + Markdown built exclusively from stored records.

Rates carry n and a confidence interval (method named). Usage and cost come from the
TOKEN_METER aggregate and inherit its status; UNKNOWN is never summed as 0. A baseline
comparison (paired by scenario) is included when the campaign declares one.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from evalkit import __version__
from evalkit.contracts import Campaign, EvalStatus, Run
from evalkit.stats import (
    dispersion,
    failure_rate,
    mean_interval,
    paired_comparison,
    proportion_interval,
    variance_decomposition,
)
from evalkit.storage.sqlite import SQLiteRepository
from evalkit.token_meter import SQLiteTokenMeter


def _valid(run_results: list[Any]) -> bool | None:
    """Run validity (docs/METRICS.md): all blocking PASS and no non-blocking FAIL.
    None when nothing was evaluated."""
    if not run_results:
        return None
    for r in run_results:
        if r.blocking and r.status is not EvalStatus.PASS:
            return False
        if r.status is EvalStatus.FAIL:
            return False
    return True


def _scenario_validity(repo: SQLiteRepository, campaign_id: str) -> dict[str, float]:
    """Per-scenario valid-run rate (pairing key for baseline comparison)."""
    rates: dict[str, list[float]] = defaultdict(list)
    for run in repo.list_runs(campaign_id):
        v = _valid(list(repo.list_results(run.run_id)))
        if v is not None:
            rates[run.scenario_id].append(1.0 if v else 0.0)
    return {k: sum(v) / len(v) for k, v in rates.items() if v}


def build_report(repo: SQLiteRepository, campaign_id: str) -> dict[str, Any]:
    campaign: Campaign = repo.get_campaign(campaign_id)
    runs: list[Run] = list(repo.list_runs(campaign_id))
    results_by_run = {r.run_id: list(repo.list_results(r.run_id)) for r in runs}
    meter = SQLiteTokenMeter(repo)

    per_scenario: dict[str, dict[str, Any]] = {}
    per_dimension: dict[str, dict[str, int]] = defaultdict(
        lambda: {"n": 0, "pass": 0, "fail": 0, "warning": 0, "inconclusive": 0, "not_evaluated": 0}
    )
    eliminatory: list[str] = []
    valid_runs = 0
    evaluated_runs = 0
    validity_by_scenario: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        entry = per_scenario.setdefault(
            run.scenario_id,
            {"version": run.scenario_version, "attempts": 0, "errors": 0, "verifications": {}},
        )
        entry["attempts"] += 1
        if run.error:
            entry["errors"] += 1
        rr = results_by_run[run.run_id]
        v = _valid(rr)
        if v is not None:
            evaluated_runs += 1
            valid_runs += int(v)
            validity_by_scenario[run.scenario_id].append(1.0 if v else 0.0)
        for res in rr:
            key = f"{res.evaluator_id}:{res.dimension.value}"
            vv = entry["verifications"].setdefault(
                key, {"n": 0, "pass": 0, "fail": 0, "other": 0, "blocking": res.blocking}
            )
            vv["n"] += 1
            if res.status is EvalStatus.PASS:
                vv["pass"] += 1
            elif res.status is EvalStatus.FAIL:
                vv["fail"] += 1
                if res.blocking:
                    eliminatory.append(f"{run.scenario_id}#{run.attempt}:{res.evaluator_id}")
            else:
                vv["other"] += 1
            d = per_dimension[res.dimension.value]
            d["n"] += 1
            d[res.status.value.lower()] += 1

    dims: dict[str, Any] = {}
    for name, d in per_dimension.items():
        evaluated = d["pass"] + d["fail"] + d["warning"]
        ci = proportion_interval(d["pass"], evaluated) if evaluated else None
        dims[name] = {
            **d,
            "pass_rate": (d["pass"] / evaluated) if evaluated else None,
            "ci": ci.model_dump(mode="json") if ci else None,
            "ci_note": "unit = verification result; repetitions of one scenario are clustered",
        }

    latencies = [r.latency_ms for r in runs if r.latency_ms is not None]
    overall = "FAIL" if eliminatory else None
    if overall is None:
        any_fail = any(d["fail"] for d in per_dimension.values())
        any_unknown = any(d["not_evaluated"] or d["inconclusive"] for d in per_dimension.values())
        overall = "FAIL" if any_fail else ("INCONCLUSIVE" if any_unknown else "PASS")
        if not per_dimension:
            overall = "NOT_EVALUATED"

    usage = meter.aggregate(campaign_id=campaign_id)
    # evaluator cost: records with evaluator_id set (kept separate from the agent's)
    evaluator_rows = repo._conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(CAST(cost_amount AS REAL)),0) AS c FROM usage_records"
        " WHERE campaign_id=? AND evaluator_id IS NOT NULL",
        (campaign_id,),
    ).fetchone()
    cost_known = usage["cost"]["known_amount"]
    cost_status = usage["cost"]["status"]
    cost_per_valid = (
        (cost_known / valid_runs)
        if valid_runs and cost_status in ("MEASURED", "ESTIMATED")
        else None
    )
    failures = sum(1 for r in runs if r.error)
    fr = failure_rate(failures, len(runs)) if runs else None
    vd = variance_decomposition({k: v for k, v in validity_by_scenario.items() if len(v) > 1})

    comparison: dict[str, Any] | None = None
    if campaign.baseline_campaign_id:
        try:
            base_rates = _scenario_validity(repo, campaign.baseline_campaign_id)
            cand_rates = {k: sum(v) / len(v) for k, v in validity_by_scenario.items() if v}
            common = sorted(set(base_rates) & set(cand_rates))
            if common:
                cmp = paired_comparison(
                    "valid_run_rate",
                    [base_rates[k] for k in common],
                    [cand_rates[k] for k in common],
                    seed=campaign.seed or 0,
                )
                comparison = {
                    "baseline_campaign_id": campaign.baseline_campaign_id,
                    "paired_scenarios": common,
                    "result": cmp.model_dump(mode="json"),
                    "equivalence_checks": _equivalence(repo, campaign),
                }
            else:
                comparison = {
                    "baseline_campaign_id": campaign.baseline_campaign_id,
                    "result": None,
                    "note": "no common scenario between baseline and candidate",
                }
        except KeyError:
            comparison = {
                "baseline_campaign_id": campaign.baseline_campaign_id,
                "result": None,
                "note": "baseline not found",
            }

    return {
        "report_version": "1.1.0",
        "evalkit_version": __version__,
        "campaign": campaign.model_dump(mode="json"),
        "overall_status": overall,
        "eliminatory_failures": eliminatory,
        "runs": len(runs),
        "runs_errored": failures,
        "runs_evaluated": evaluated_runs,
        "valid_runs": valid_runs,
        "valid_run_rate": (
            proportion_interval(valid_runs, evaluated_runs).model_dump(mode="json")
            if evaluated_runs
            else None
        ),
        "error_rate": fr.model_dump(mode="json") if fr else None,
        "scenarios": per_scenario,
        "dimensions": dims,
        "latency_ms": {
            **dispersion(latencies),
            "ci_mean": mean_interval(latencies).model_dump(mode="json")
            if len(latencies) >= 2
            else None,
        },
        "usage": usage,
        "cost": {
            "status": cost_status,
            "known_amount": cost_known,
            "currency": usage["cost"]["currency"],
            "cost_per_valid_run": cost_per_valid,
            "valid_run_definition": "all blocking verifications PASS and no non-blocking FAIL",
            "evaluator_cost_known": float(evaluator_rows["c"]) if evaluator_rows else 0.0,
            "evaluator_records": int(evaluator_rows["n"]) if evaluator_rows else 0,
            "price_snapshot_ids": campaign.price_snapshot_ids,
        },
        "variance": vd.model_dump(mode="json"),
        "comparison": comparison,
        "validity": [
            "results come from the adapter declared in the campaign; a simulated adapter is "
            "not a production validation",
            "intervals use the verification result (or run) as unit; repetitions of one "
            "scenario are clustered, so campaign-level claims should weight by scenario",
            f"profile {campaign.profile.value}: selection rules are recorded in the "
            "campaign.started audit event",
            "cost figures carry the TOKEN_METER status; UNKNOWN records are counted, not summed",
        ],
    }


def _equivalence(repo: SQLiteRepository, campaign: Campaign) -> list[str]:
    """Warnings when baseline and candidate are not comparable (docs/SCORING.md §4)."""
    warnings: list[str] = []
    try:
        base = repo.get_campaign(campaign.baseline_campaign_id or "")
    except KeyError:
        return ["baseline campaign not found"]
    if base.profile is not campaign.profile:
        warnings.append(f"profiles differ: {base.profile.value} vs {campaign.profile.value}")
    if base.agent_id != campaign.agent_id:
        warnings.append("different agents")
    if base.evalkit_version != campaign.evalkit_version:
        warnings.append("different EVALKIT versions")
    base_versions = {(r.scenario_id, r.scenario_version) for r in repo.list_runs(base.campaign_id)}
    cand_versions = {
        (r.scenario_id, r.scenario_version) for r in repo.list_runs(campaign.campaign_id)
    }
    if {s for s, _ in base_versions} & {
        s for s, _ in cand_versions
    } and base_versions != cand_versions:
        warnings.append("scenario versions differ between campaigns")
    return warnings


def _fmt_ci(ci: dict[str, Any] | None) -> str:
    if not ci:
        return "n/a"
    return f"[{ci['low']:.2f}, {ci['high']:.2f}] {ci['method']} n={ci['n']}"


def render_markdown(report: dict[str, Any]) -> str:
    c = report["campaign"]
    lines = [
        f"# EVALKIT campaign report — {c['campaign_id']}",
        "",
        f"- Project / agent: `{c['project_id']}` / `{c['agent_id']}` v{c['agent_version']}",
        f"- Profile: {c['profile']} · status: {c['status']} · dry run: {c['dry_run']}",
        f"- Overall evaluation status: **{report['overall_status']}**",
        f"- Runs: {report['runs']} (errored: {report['runs_errored']}, valid: "
        f"{report['valid_runs']}/{report['runs_evaluated']}; "
        f"rate {_fmt_ci(report['valid_run_rate'])})",
        f"- Error rate: {_fmt_ci(report['error_rate'])}",
        f"- EVALKIT {report['evalkit_version']} · report v{report['report_version']}",
        "",
        "## Eliminatory failures",
        "",
    ]
    if report["eliminatory_failures"]:
        lines += [f"- {e}" for e in report["eliminatory_failures"]]
    else:
        lines.append("None.")
    lines += [
        "",
        "## Dimensions",
        "",
        "| dimension | n | pass | fail | other | pass rate | 95 % CI |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, d in report["dimensions"].items():
        other = d["warning"] + d["inconclusive"] + d["not_evaluated"]
        rate = "n/a" if d["pass_rate"] is None else f"{d['pass_rate']:.0%}"
        lines.append(
            f"| {name} | {d['n']} | {d['pass']} | {d['fail']} | {other} | {rate} "
            f"| {_fmt_ci(d['ci'])} |"
        )
    lines += [
        "",
        "## Scenarios",
        "",
        "| scenario | attempts | errors | verification | n | pass | fail | blocking |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for sid, s in report["scenarios"].items():
        for key, v in s["verifications"].items():
            lines.append(
                f"| {sid} v{s['version']} | {s['attempts']} | {s['errors']} | {key} | {v['n']} | "
                f"{v['pass']} | {v['fail']} | {'yes' if v['blocking'] else ''} |"
            )
    u, cost, lat = report["usage"], report["cost"], report["latency_ms"]
    lines += [
        "",
        "## Usage and cost",
        "",
        f"- Usage status: **{u['status']}** — records {u['records']}",
        f"- Tokens (known part): {u['tokens']}",
        f"- Cost: **{cost['status']}** — known amount {cost['known_amount']}"
        f" {cost['currency'] or ''} (price snapshot: {cost['price_snapshot_ids'] or 'none'})",
        f"- Cost per valid run: {cost['cost_per_valid_run']} ({cost['valid_run_definition']})",
        f"- Evaluator cost (separate): {cost['evaluator_cost_known']}"
        f" over {cost['evaluator_records']} records",
        f"- Latency ms: n={lat['n']} mean={lat['mean']} p50={lat['p50']} p95={lat['p95']}"
        f" CI(mean)={_fmt_ci(lat['ci_mean'])}",
        "",
        "## Variability",
        "",
        f"- {report['variance']}",
    ]
    cmp = report.get("comparison")
    if cmp:
        lines += [
            "",
            "## Comparison with baseline",
            "",
            f"- Baseline: {cmp['baseline_campaign_id']}",
        ]
        if cmp.get("result"):
            r = cmp["result"]
            lines += [
                f"- Metric {r['metric']}: baseline {r['baseline_estimate']:.3f} → candidate "
                f"{r['candidate_estimate']:.3f} (diff {r['difference']:+.3f},"
                f" CI {_fmt_ci(r['ci'])})",
                f"- Conclusion: **{r['conclusion']}** — {r['rationale']}",
                f"- Effect size ({r['effect_size_method']}): {r['effect_size']};"
                f" p (sign test): {r['p_value']}",
            ]
            for w in cmp.get("equivalence_checks", []):
                lines.append(f"- WARNING non-equivalence: {w}")
        else:
            lines.append(f"- {cmp.get('note')}")
    lines += ["", "## Validity limits", ""]
    lines += [f"- {v}" for v in report["validity"]]
    return "\n".join(lines) + "\n"


def write_report(repo: SQLiteRepository, campaign_id: str, out_dir: Path) -> tuple[Path, Path]:
    report = build_report(repo, campaign_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{campaign_id}.json"
    md_path = out_dir / f"{campaign_id}.md"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
