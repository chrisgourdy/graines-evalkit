"""SCORING_ENGINE — builds a persisted Scorecard for a campaign from stored results only.

Rules (docs/SCORING.md):
* each dimension scored separately with its own measurement kind and interval;
* eliminatory (blocking) failures are listed independently and force overall FAIL;
* unknown never becomes 0 or PASS: NOT_EVALUATED dimensions are listed in
  ``missing_dimensions`` and excluded from any aggregate;
* an aggregate is computed only when the project provides weights, and then the formula,
  weights and exclusions are printed in ``aggregate_formula``;
* validity controls add warnings (underpowered, wide interval, coverage, non-equivalent
  comparison, evaluator drift, overfitting signal, inconclusive comparison).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from evalkit import __version__
from evalkit.contracts import (
    Campaign,
    Criticality,
    DatasetKind,
    Dimension,
    DimensionScore,
    EvalStatus,
    EvaluationResult,
    EventType,
    MeasurementKind,
    Run,
    Scorecard,
    new_id,
    utcnow,
)
from evalkit.contracts.scorecard import ConfidenceInterval
from evalkit.stats import MIN_N_PROPORTION, paired_comparison, proportion_interval
from evalkit.storage.sqlite import SQLiteRepository
from evalkit.token_meter import SQLiteTokenMeter

WIDE_INTERVAL = 0.5
"""A pass-rate interval wider than this is flagged as a misleading metric."""


@dataclass
class _DimAcc:
    n: int = 0
    passed: int = 0
    failed: int = 0
    warning: int = 0
    inconclusive: int = 0
    not_evaluated: int = 0
    critical_failures: int = 0
    kinds: set[MeasurementKind] | None = None
    scores: list[float] | None = None


def _measurement(kinds: set[MeasurementKind]) -> MeasurementKind:
    for kind in (
        MeasurementKind.HUMAN,
        MeasurementKind.LLM_JUDGED,
        MeasurementKind.STATISTICAL,
        MeasurementKind.OBJECTIVE,
    ):
        if kind in kinds:
            return kind
    return MeasurementKind.UNAVAILABLE


def _dimension_status(acc: _DimAcc) -> EvalStatus:
    evaluated = acc.passed + acc.failed + acc.warning
    if evaluated == 0:
        return EvalStatus.NOT_EVALUATED
    if acc.failed:
        return EvalStatus.FAIL
    if acc.inconclusive or acc.not_evaluated:
        return EvalStatus.INCONCLUSIVE
    if acc.warning:
        return EvalStatus.WARNING
    return EvalStatus.PASS


def _overall(
    dimensions: list[DimensionScore], eliminatory: list[str], required: set[Dimension]
) -> EvalStatus:
    if eliminatory:
        return EvalStatus.FAIL
    statuses = {d.dimension: d.status for d in dimensions}
    for dim in required:
        if statuses.get(dim, EvalStatus.NOT_EVALUATED) in (
            EvalStatus.NOT_EVALUATED,
            EvalStatus.INCONCLUSIVE,
        ):
            return EvalStatus.INCONCLUSIVE
    if any(s is EvalStatus.FAIL for s in statuses.values()):
        return EvalStatus.FAIL
    if any(s is EvalStatus.INCONCLUSIVE for s in statuses.values()):
        return EvalStatus.INCONCLUSIVE
    if any(s is EvalStatus.WARNING for s in statuses.values()):
        return EvalStatus.WARNING
    return EvalStatus.PASS if dimensions else EvalStatus.NOT_EVALUATED


def _scenario_valid_rates(repo: SQLiteRepository, campaign_id: str) -> dict[str, float]:
    rates: dict[str, list[float]] = defaultdict(list)
    for run in repo.list_runs(campaign_id):
        results = list(repo.list_results(run.run_id))
        if not results:
            continue
        valid = all(
            (r.status is EvalStatus.PASS) if r.blocking else (r.status is not EvalStatus.FAIL)
            for r in results
        )
        rates[run.scenario_id].append(1.0 if valid else 0.0)
    return {k: sum(v) / len(v) for k, v in rates.items()}


def build_scorecard(
    repo: SQLiteRepository,
    campaign_id: str,
    *,
    weights: dict[str, float] | None = None,
    required_dimensions: set[Dimension] | None = None,
    persist: bool = True,
) -> Scorecard:
    campaign: Campaign = repo.get_campaign(campaign_id)
    runs: list[Run] = list(repo.list_runs(campaign_id))
    results: dict[str, list[EvaluationResult]] = {
        r.run_id: list(repo.list_results(r.run_id)) for r in runs
    }
    scenario_crit: dict[str, Criticality] = {}
    scenario_dataset: dict[str, DatasetKind] = {}
    for run in runs:
        try:
            s = repo.get_scenario(run.scenario_id, run.scenario_version)
            scenario_crit[run.scenario_id] = s.criticality
            scenario_dataset[run.scenario_id] = s.dataset
        except KeyError:
            pass

    accs: dict[Dimension, _DimAcc] = defaultdict(_DimAcc)
    eliminatory: list[str] = []
    evaluator_versions: dict[str, set[str]] = defaultdict(set)
    for run in runs:
        for res in results[run.run_id]:
            acc = accs[res.dimension]
            acc.kinds = acc.kinds or set()
            acc.scores = acc.scores if acc.scores is not None else []
            acc.n += 1
            acc.kinds.add(res.measurement)
            evaluator_versions[res.evaluator_id].add(res.evaluator_version)
            if res.score is not None:
                acc.scores.append(res.score)
            if res.status is EvalStatus.PASS:
                acc.passed += 1
            elif res.status is EvalStatus.FAIL:
                acc.failed += 1
                if res.blocking:
                    eliminatory.append(f"{run.scenario_id}#{run.attempt}:{res.evaluator_id}")
                if scenario_crit.get(run.scenario_id) is Criticality.CRITICAL:
                    acc.critical_failures += 1
            elif res.status is EvalStatus.WARNING:
                acc.warning += 1
            elif res.status is EvalStatus.INCONCLUSIVE:
                acc.inconclusive += 1
            else:
                acc.not_evaluated += 1

    warnings: list[str] = []
    dimensions: list[DimensionScore] = []
    missing: list[Dimension] = []
    for dim, acc in sorted(accs.items(), key=lambda kv: kv[0].value):
        evaluated = acc.passed + acc.failed + acc.warning
        status = _dimension_status(acc)
        ci: ConfidenceInterval | None = None
        pass_rate: float | None = None
        if evaluated:
            pass_rate = acc.passed / evaluated
            iv = proportion_interval(acc.passed, evaluated)
            ci = ConfidenceInterval(
                low=iv.low, high=iv.high, level=iv.level, method=iv.method, n=iv.n
            )
            if evaluated < MIN_N_PROPORTION:
                warnings.append(f"{dim.value}: underpowered (n={evaluated} < {MIN_N_PROPORTION})")
            if iv.high - iv.low > WIDE_INTERVAL:
                warnings.append(
                    f"{dim.value}: interval width {iv.high - iv.low:.2f} > {WIDE_INTERVAL}:"
                    " metric not informative yet"
                )
        else:
            missing.append(dim)
        kinds = acc.kinds or set()
        dimensions.append(
            DimensionScore(
                dimension=dim,
                status=status,
                measurement=_measurement(kinds) if evaluated else MeasurementKind.UNAVAILABLE,
                pass_rate=pass_rate,
                mean_score=(sum(acc.scores) / len(acc.scores)) if acc.scores else None,
                ci=ci,
                n_runs=len(runs),
                n_evaluated=evaluated,
                critical_failures=acc.critical_failures,
                note=None
                if not (acc.inconclusive or acc.not_evaluated)
                else f"{acc.inconclusive + acc.not_evaluated} result(s) without conclusion",
            )
        )

    # Coverage control: CRITICAL/HIGH scenarios of this agent that the campaign did not run.
    all_scenarios = list(repo.list_scenarios(campaign.project_id, campaign.agent_id))
    ran = {r.scenario_id for r in runs}
    not_run = sorted(
        s.scenario_id
        for s in all_scenarios
        if s.criticality in (Criticality.CRITICAL, Criticality.HIGH) and s.scenario_id not in ran
    )
    if not_run:
        warnings.append(
            f"coverage: {len(not_run)} CRITICAL/HIGH scenario(s) not executed: {not_run[:5]}"
        )
    for ev, versions in evaluator_versions.items():
        if len(versions) > 1:
            warnings.append(f"evaluator {ev}: several versions in one campaign {sorted(versions)}")

    # Baseline comparison and derived validity controls.
    regressions: list[str] = []
    if campaign.baseline_campaign_id:
        try:
            base = repo.get_campaign(campaign.baseline_campaign_id)
        except KeyError:
            base = None
            warnings.append("baseline campaign not found")
        if base is not None:
            if base.profile is not campaign.profile:
                warnings.append(
                    "non-equivalent comparison: profiles "
                    f"{base.profile.value} vs {campaign.profile.value}"
                )
            base_rates = _scenario_valid_rates(repo, base.campaign_id)
            cand_rates = _scenario_valid_rates(repo, campaign.campaign_id)
            common = sorted(set(base_rates) & set(cand_rates))
            if common:
                cmp = paired_comparison(
                    "valid_run_rate",
                    [base_rates[k] for k in common],
                    [cand_rates[k] for k in common],
                    seed=campaign.seed or 0,
                )
                if cmp.conclusion is EvalStatus.FAIL:
                    regressions.append(f"valid_run_rate: {cmp.rationale}")
                elif cmp.conclusion is EvalStatus.INCONCLUSIVE:
                    warnings.append(f"comparison with baseline inconclusive: {cmp.rationale}")
                for sid in common:
                    if cand_rates[sid] < base_rates[sid]:
                        regressions.append(f"{sid}: {base_rates[sid]:.2f} -> {cand_rates[sid]:.2f}")
                # overfitting signal: DEVELOPMENT improves while HOLDOUT does not
                dev = [
                    sid for sid in common if scenario_dataset.get(sid) is DatasetKind.DEVELOPMENT
                ]
                hold = [sid for sid in common if scenario_dataset.get(sid) is DatasetKind.HOLDOUT]
                if dev and hold:
                    dev_gain = sum(cand_rates[s] - base_rates[s] for s in dev) / len(dev)
                    hold_gain = sum(cand_rates[s] - base_rates[s] for s in hold) / len(hold)
                    if dev_gain > 0 and hold_gain <= 0:
                        warnings.append(
                            f"possible overfitting: DEVELOPMENT gain {dev_gain:+.2f}"
                            f" not reproduced on HOLDOUT ({hold_gain:+.2f})"
                        )
            else:
                warnings.append("no common scenario with baseline: comparison impossible")
            # evaluator drift between campaigns
            base_versions: dict[str, set[str]] = defaultdict(set)
            for r in repo.list_runs(base.campaign_id):
                for res in repo.list_results(r.run_id):
                    base_versions[res.evaluator_id].add(res.evaluator_version)
            for ev, versions in evaluator_versions.items():
                if ev in base_versions and base_versions[ev] != versions:
                    warnings.append(
                        f"evaluator drift: {ev} {sorted(base_versions[ev])} -> {sorted(versions)}"
                    )

    # Optional aggregate with visible formula.
    aggregate: float | None = None
    formula: str | None = None
    if weights:
        used = [
            (d, weights[d.dimension.value])
            for d in dimensions
            if d.pass_rate is not None and d.dimension.value in weights
        ]
        excluded = [d.value for d in missing] + [
            d.dimension.value
            for d in dimensions
            if d.pass_rate is not None and d.dimension.value not in weights
        ]
        total_w = sum(w for _, w in used)
        if used and total_w > 0:
            aggregate = sum(d.pass_rate * w for d, w in used if d.pass_rate is not None) / total_w
            formula = (
                "weighted mean of pass rates: "
                + " + ".join(f"{w:g}*{d.dimension.value}" for d, w in used)
                + f" / {total_w:g}; excluded (no data or no weight): {excluded or 'none'}"
                + "; eliminatory failures are NOT absorbed by this aggregate"
            )

    meter = SQLiteTokenMeter(repo)
    usage = meter.aggregate(campaign_id=campaign_id)
    latencies = [r.latency_ms for r in runs if r.latency_ms is not None]
    required = required_dimensions or set()
    card = Scorecard(
        scorecard_id=new_id("scd"),
        project_id=campaign.project_id,
        agent_id=campaign.agent_id,
        agent_version=campaign.agent_version,
        campaign_id=campaign_id,
        generated_at=utcnow(),
        evalkit_version=__version__,
        overall_status=_overall(dimensions, eliminatory, required),
        eliminatory_failures=eliminatory,
        dimensions=dimensions,
        aggregate_score=aggregate,
        aggregate_formula=formula,
        missing_dimensions=missing,
        total_cost=usage["cost"]["known_amount"]
        if usage["cost"]["status"] not in ("NO_DATA", "UNKNOWN")
        else None,
        currency=usage["cost"]["currency"] or "USD",
        cost_status=usage["cost"]["status"],
        mean_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
        baseline_campaign_id=campaign.baseline_campaign_id,
        regressions=regressions,
        validity_warnings=warnings,
    )
    if persist:
        with repo.transaction():
            repo.save_scorecard(card)
        from evalkit.audit import make_event

        if regressions:
            repo.emit(
                make_event(
                    EventType.REGRESSION_DETECTED,
                    component="scoring",
                    project_id=card.project_id,
                    agent_id=card.agent_id,
                    agent_version=card.agent_version,
                    campaign_id=campaign_id,
                    payload={"scorecard_id": card.scorecard_id, "regressions": regressions[:10]},
                )
            )
        repo.emit(
            make_event(
                EventType.EVALUATION_RESULT,
                component="scoring",
                project_id=card.project_id,
                agent_id=card.agent_id,
                agent_version=card.agent_version,
                campaign_id=campaign_id,
                status=card.overall_status.value,
                payload={"scorecard_id": card.scorecard_id, "warnings": len(warnings)},
            )
        )
    return card
