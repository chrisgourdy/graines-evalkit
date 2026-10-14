"""Campaign report (Phase 2): JSON + Markdown built exclusively from stored records.

No confidence intervals yet (Phase 3): every rate is shown with its n and the note
"CI: not yet computed". Unknown usage is never summed as 0.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from evalkit import __version__
from evalkit.contracts import Campaign, EvalStatus, Run, UsageSource
from evalkit.storage.sqlite import SQLiteRepository


def _usage_totals(runs: list[Run]) -> dict[str, Any]:
    totals: dict[str, int] = defaultdict(int)
    unknown = 0
    estimated = 0
    reported = 0
    for run in runs:
        for u in run.usage:
            if u.source is UsageSource.UNKNOWN:
                unknown += 1
                continue
            if u.source is UsageSource.ESTIMATED:
                estimated += 1
            else:
                reported += 1
            for name in (
                "input_tokens",
                "output_tokens",
                "cached_input_tokens",
                "cache_creation_tokens",
                "reasoning_tokens",
            ):
                v = getattr(u, name)
                if v is not None:
                    totals[name] += v
            bt = u.billable_total()
            if bt is not None:
                totals["billable_total"] += bt
    status = "UNKNOWN" if unknown else ("ESTIMATED" if estimated else "REPORTED")
    if unknown and (reported or estimated):
        status = "PARTIAL"
    return {
        "status": status,
        "records": {"reported": reported, "estimated": estimated, "unknown": unknown},
        "known_part": dict(totals),
        "note": (
            "totals cover REPORTED/ESTIMATED records only; UNKNOWN records are counted, not summed"
            if unknown
            else "all records REPORTED"
            if not estimated
            else "contains ESTIMATED records (method recorded per record)"
        ),
    }


def build_report(repo: SQLiteRepository, campaign_id: str) -> dict[str, Any]:
    campaign: Campaign = repo.get_campaign(campaign_id)
    runs = list(repo.list_runs(campaign_id))
    results_by_run = {r.run_id: list(repo.list_results(r.run_id)) for r in runs}

    per_scenario: dict[str, dict[str, Any]] = {}
    per_dimension: dict[str, dict[str, int]] = defaultdict(
        lambda: {"n": 0, "pass": 0, "fail": 0, "warning": 0, "inconclusive": 0, "not_evaluated": 0}
    )
    eliminatory: list[str] = []
    for run in runs:
        entry = per_scenario.setdefault(
            run.scenario_id,
            {"version": run.scenario_version, "attempts": 0, "errors": 0, "verifications": {}},
        )
        entry["attempts"] += 1
        if run.error:
            entry["errors"] += 1
        for res in results_by_run[run.run_id]:
            key = f"{res.evaluator_id}:{res.dimension.value}"
            v = entry["verifications"].setdefault(
                key, {"n": 0, "pass": 0, "fail": 0, "other": 0, "blocking": res.blocking}
            )
            v["n"] += 1
            if res.status is EvalStatus.PASS:
                v["pass"] += 1
            elif res.status is EvalStatus.FAIL:
                v["fail"] += 1
                if res.blocking:
                    eliminatory.append(f"{run.scenario_id}#{run.attempt}:{res.evaluator_id}")
            else:
                v["other"] += 1
            d = per_dimension[res.dimension.value]
            d["n"] += 1
            d[res.status.value.lower()] += 1

    dims: dict[str, Any] = {}
    for name, d in per_dimension.items():
        evaluated = d["pass"] + d["fail"] + d["warning"]
        dims[name] = {
            **d,
            "pass_rate": (d["pass"] / evaluated) if evaluated else None,
            "ci": None,
            "ci_note": "not yet computed (statistical engine arrives in Phase 3)",
        }

    latencies = [r.latency_ms for r in runs if r.latency_ms is not None]
    overall = "FAIL" if eliminatory else None
    if overall is None:
        any_fail = any(d["fail"] for d in per_dimension.values())
        any_unknown = any(d["not_evaluated"] or d["inconclusive"] for d in per_dimension.values())
        overall = "FAIL" if any_fail else ("INCONCLUSIVE" if any_unknown else "PASS")
        if not per_dimension:
            overall = "NOT_EVALUATED"

    return {
        "report_version": "1.0.0",
        "evalkit_version": __version__,
        "campaign": campaign.model_dump(mode="json"),
        "overall_status": overall,
        "eliminatory_failures": eliminatory,
        "runs": len(runs),
        "runs_errored": sum(1 for r in runs if r.error),
        "scenarios": per_scenario,
        "dimensions": dims,
        "latency_ms": {
            "n": len(latencies),
            "mean": (sum(latencies) / len(latencies)) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "usage": _usage_totals(runs),
        "cost": {"status": "UNKNOWN", "note": "cost engine arrives in Phase 3"},
        "validity": [
            "results come from the adapter declared in the campaign; a simulated adapter is "
            "not a production validation",
            "no confidence intervals in this report version; rates are raw proportions with n",
            f"profile {campaign.profile.value}: selection rules are recorded in the "
            "campaign.started audit event",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    c = report["campaign"]
    lines = [
        f"# EVALKIT campaign report — {c['campaign_id']}",
        "",
        f"- Project / agent: `{c['project_id']}` / `{c['agent_id']}` v{c['agent_version']}",
        f"- Profile: {c['profile']} · status: {c['status']} · dry run: {c['dry_run']}",
        f"- Overall evaluation status: **{report['overall_status']}**",
        f"- Runs: {report['runs']} (errored: {report['runs_errored']})",
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
        "| dimension | n | pass | fail | other | pass rate | CI |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, d in report["dimensions"].items():
        other = d["warning"] + d["inconclusive"] + d["not_evaluated"]
        rate = "n/a" if d["pass_rate"] is None else f"{d['pass_rate']:.0%}"
        lines.append(
            f"| {name} | {d['n']} | {d['pass']} | {d['fail']} | {other} | {rate} "
            "| not yet computed |"
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
    u = report["usage"]
    lines += [
        "",
        "## Usage and cost",
        "",
        f"- Usage status: **{u['status']}** — {u['note']}",
        f"- Records: {u['records']}",
        f"- Known part: {u['known_part']}",
        f"- Cost: {report['cost']['status']} — {report['cost']['note']}",
        f"- Latency: n={report['latency_ms']['n']}, mean={report['latency_ms']['mean']}, "
        f"max={report['latency_ms']['max']}",
        "",
        "## Validity limits",
        "",
    ]
    lines += [f"- {v}" for v in report["validity"]]
    return "\n".join(lines) + "\n"


def write_report(repo: SQLiteRepository, campaign_id: str, out_dir: Path) -> tuple[Path, Path]:
    report = build_report(repo, campaign_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{campaign_id}.json"
    md_path = out_dir / f"{campaign_id}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
