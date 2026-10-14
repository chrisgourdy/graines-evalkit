"""Seeded statistical property tests (self-evaluation of the statistical engine)."""

from __future__ import annotations

import numpy as np
import pytest

from evalkit.contracts import EvalStatus
from evalkit.stats import (
    MIN_PAIRS,
    bootstrap_bca,
    cliffs_delta,
    clopper_pearson,
    cohen_h,
    dispersion,
    failure_rate,
    holm,
    jeffreys,
    mean_interval,
    mean_t_interval,
    paired_comparison,
    proportion_comparison,
    proportion_interval,
    rule_of_three,
    stratified_sample,
    variance_decomposition,
    wilson,
)

pytestmark = pytest.mark.statistical


@pytest.mark.parametrize(("p", "n"), [(0.3, 20), (0.5, 50), (0.9, 30)])
def test_wilson_coverage_close_to_nominal(p: float, n: int) -> None:
    rng = np.random.default_rng(123)
    sims = 10_000
    ks = rng.binomial(n, p, size=sims)
    covered = sum(1 for k in ks if (lambda ci: ci.low <= p <= ci.high)(wilson(int(k), n)))
    coverage = covered / sims
    # Wilson oscillates around nominal for discrete data (over-covers near p→1): tolerance ±3 pts
    assert 0.92 <= coverage <= 0.98, coverage


def test_clopper_pearson_is_conservative() -> None:
    rng = np.random.default_rng(7)
    p, n, sims = 0.2, 15, 5_000
    ks = rng.binomial(n, p, size=sims)
    coverage = np.mean(
        [clopper_pearson(int(k), n).low <= p <= clopper_pearson(int(k), n).high for k in ks]
    )
    assert coverage >= 0.95


def test_interval_shapes_and_flags() -> None:
    ci = wilson(3, 4)
    assert "underpowered" in " ".join(ci.warnings)
    assert proportion_interval(0, 3).method == "clopper_pearson"
    assert proportion_interval(10, 20).method == "wilson"
    assert proportion_interval(20, 20).method == "clopper_pearson"
    r3 = rule_of_three(100)
    assert r3.estimate == 0.0 and 0.029 < r3.high < 0.031
    j = jeffreys(0, 10)
    assert j.low == 0.0 and 0 < j.high < 0.3
    assert wilson(0, 0).n == 0 and wilson(0, 0).high == 1.0
    with pytest.raises(ValueError, match="invalid counts"):
        wilson(5, 3)


def test_mean_interval_route_and_bootstrap_coverage() -> None:
    rng = np.random.default_rng(42)
    normal = rng.normal(10, 2, size=40)
    assert mean_interval(normal.tolist()).method == "t"
    skewed = rng.exponential(1.0, size=15)
    assert mean_interval(skewed.tolist()).method == "bootstrap_bca"
    assert "CLT approximation weak" in " ".join(mean_t_interval(skewed.tolist()).warnings)
    # bootstrap coverage of the mean of an exponential(1): true mean 1
    hits = 0
    sims = 300
    for s in range(sims):
        sample = np.random.default_rng(s).exponential(1.0, size=25)
        ci = bootstrap_bca(sample.tolist(), n_resamples=600, seed=s)
        hits += ci.low <= 1.0 <= ci.high
    assert 0.88 <= hits / sims <= 0.98


def test_bootstrap_is_deterministic_for_a_seed() -> None:
    data = [1.0, 2.0, 2.5, 3.0, 10.0, 4.0]
    a, b = bootstrap_bca(data, seed=3), bootstrap_bca(data, seed=3)
    assert (a.low, a.high) == (b.low, b.high)
    assert bootstrap_bca([5.0, 5.0, 5.0]).warnings


def test_paired_comparison_detects_regression_and_improvement() -> None:
    base = [0.9] * 12
    worse = [0.5] * 6 + [0.6] * 6
    res = paired_comparison("pass_rate", base, worse)
    assert res.conclusion is EvalStatus.FAIL and res.ci and res.ci.high < 0
    better = [1.0] * 12
    res2 = paired_comparison("pass_rate", base, better)
    assert res2.conclusion is EvalStatus.PASS and "improvement" in res2.rationale
    assert res2.effect_size_method == "cohen_d"


def test_paired_comparison_inconclusive_when_underpowered_or_spanning() -> None:
    small = paired_comparison("m", [0.5, 0.6, 0.7], [0.6, 0.7, 0.8])
    assert small.n_baseline < MIN_PAIRS and small.conclusion is EvalStatus.INCONCLUSIVE
    rng = np.random.default_rng(1)
    base = rng.normal(0.7, 0.1, size=10)
    cand = base + rng.normal(0.0, 0.3, size=10)
    noisy = paired_comparison("m", base.tolist(), cand.tolist())
    assert noisy.conclusion is EvalStatus.INCONCLUSIVE
    with pytest.raises(ValueError, match="aligned"):
        paired_comparison("m", [1.0], [1.0, 2.0])


def test_no_difference_is_not_equivalence() -> None:
    same = paired_comparison("m", [0.8] * 10, [0.8] * 10, margin=0.05)
    assert same.conclusion is EvalStatus.PASS
    assert "not evidence of equivalence" in same.rationale


def test_proportion_comparison_unpaired_flagged() -> None:
    res = proportion_comparison("pass_rate", (18, 20), (9, 20))
    assert res.conclusion is EvalStatus.FAIL and res.paired is False
    assert res.ci and "unpaired" in " ".join(res.ci.warnings)
    assert res.p_value is not None and res.p_value < 0.01
    assert proportion_comparison("m", (0, 0), (1, 2)).conclusion is EvalStatus.INCONCLUSIVE


def test_effect_sizes_and_holm() -> None:
    assert cohen_h(0.5, 0.5) == 0.0
    assert cliffs_delta([1, 2, 3], [4, 5, 6]) == 1.0
    adj = holm([0.01, 0.04, 0.03])
    assert adj == [0.03, 0.04, 0.06] or adj == [0.03, 0.06, 0.06]
    assert all(a >= p for a, p in zip(adj, [0.01, 0.04, 0.03], strict=True))
    assert holm([]) == []


def test_montecarlo_helpers() -> None:
    items = list(range(20))
    strata = ["CRITICAL"] * 2 + ["LOW"] * 18
    picked = stratified_sample(items, strata, 0.2, seed=1)
    assert 0 in picked or 1 in picked  # critical stratum never dropped
    assert stratified_sample(items, strata, 0.2, seed=1) == picked
    d = dispersion([1.0, 2.0, 3.0, 4.0])
    assert d["n"] == 4 and d["cv"] and d["p95"]
    assert dispersion([])["mean"] is None
    fr = failure_rate(0, 50)
    assert fr.method == "rule_of_three"
    assert failure_rate(3, 50).method == "wilson"
    vd = variance_decomposition({"a": [1, 1, 1], "b": [3, 3, 3]})
    assert vd.between_scenarios == 1.0 and vd.between_generations == 0.0
    assert variance_decomposition({"a": [1]}).between_scenarios is None
