"""Version comparisons. Paired by scenario whenever possible; INCONCLUSIVE is first-class.

Decision rule (documented in docs/STATISTICAL_METHODS.md §4): with ``higher_is_better``,
the conclusion is FAIL (regression) when the CI of (candidate - baseline) lies entirely below
-margin, PASS (no regression; improvement if CI above +margin) when it lies entirely above
-margin AND the sample is not underpowered, and INCONCLUSIVE otherwise. Absence of a detected
difference never becomes "equivalent".
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from scipy import stats as sps

from evalkit.contracts import EvalStatus
from evalkit.stats.interfaces import ComparisonResult, IntervalResult
from evalkit.stats.intervals import DEFAULT_LEVEL

MIN_PAIRS = 5


def cohen_h(p1: float, p2: float) -> float:
    """Effect size for two proportions."""
    return 2 * math.asin(math.sqrt(p2)) - 2 * math.asin(math.sqrt(p1))


def cohen_d(a: Sequence[float], b: Sequence[float]) -> float | None:
    x, y = np.asarray(a, float), np.asarray(b, float)
    if x.size < 2 or y.size < 2:
        return None
    pooled = math.sqrt(
        ((x.size - 1) * x.var(ddof=1) + (y.size - 1) * y.var(ddof=1)) / (x.size + y.size - 2)
    )
    return float((y.mean() - x.mean()) / pooled) if pooled > 0 else 0.0


def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> float | None:
    x, y = np.asarray(a, float), np.asarray(b, float)
    if x.size == 0 or y.size == 0:
        return None
    gt = float(np.sum(y[:, None] > x[None, :]))
    lt = float(np.sum(y[:, None] < x[None, :]))
    return (gt - lt) / (x.size * y.size)


def holm(p_values: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values (controls FWER)."""
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        val = min(1.0, (m - rank) * p_values[i])
        running = max(running, val)
        adjusted[i] = running
    return adjusted


def _conclude(
    ci: IntervalResult | None, *, margin: float, underpowered: bool, higher_is_better: bool
) -> tuple[EvalStatus, str]:
    if ci is None or math.isnan(ci.low) or math.isnan(ci.high):
        return EvalStatus.INCONCLUSIVE, "no interval could be computed"
    low, high = (ci.low, ci.high) if higher_is_better else (-ci.high, -ci.low)
    if high < -margin:
        return (
            EvalStatus.FAIL,
            f"CI [{ci.low:.4f}, {ci.high:.4f}] entirely below -{margin}: regression",
        )
    if underpowered:
        return (
            EvalStatus.INCONCLUSIVE,
            "sample underpowered: no regression detected, equivalence not shown",
        )
    if low > margin:
        return (
            EvalStatus.PASS,
            f"CI [{ci.low:.4f}, {ci.high:.4f}] entirely above +{margin}: improvement",
        )
    if low > -margin:
        return EvalStatus.PASS, (
            f"CI [{ci.low:.4f}, {ci.high:.4f}] excludes a regression larger than {margin}; "
            "not evidence of equivalence beyond that margin"
        )
    return (
        EvalStatus.INCONCLUSIVE,
        f"CI [{ci.low:.4f}, {ci.high:.4f}] spans -{margin}: cannot decide",
    )


def paired_comparison(
    metric: str,
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    margin: float = 0.0,
    level: float = DEFAULT_LEVEL,
    higher_is_better: bool = True,
    n_resamples: int = 4000,
    seed: int = 0,
) -> ComparisonResult:
    """Paired (same scenarios, same order) comparison via bootstrap of per-pair differences,
    with a sign test p-value as robustness check."""
    x, y = np.asarray(baseline, float), np.asarray(candidate, float)
    if x.size != y.size:
        msg = "paired comparison needs equal-length, aligned samples"
        raise ValueError(msg)
    n = int(x.size)
    diffs = y - x
    ci: IntervalResult | None = None
    p_value: float | None = None
    if n >= 2:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, n, size=(n_resamples, n))
        boots = diffs[idx].mean(axis=1)
        alpha = 1 - level
        ci = IntervalResult(
            estimate=float(diffs.mean()),
            low=float(np.quantile(boots, alpha / 2)),
            high=float(np.quantile(boots, 1 - alpha / 2)),
            level=level,
            method="paired_bootstrap_percentile",
            n=n,
            assumptions=["pairs are exchangeable; scenario is the sampling unit"],
        )
        nonzero = diffs[diffs != 0]
        if nonzero.size > 0:
            pos = int(np.sum(nonzero > 0))
            p_value = float(sps.binomtest(pos, nonzero.size, 0.5).pvalue)
        else:
            p_value = 1.0
    underpowered = n < MIN_PAIRS
    conclusion, rationale = _conclude(
        ci, margin=margin, underpowered=underpowered, higher_is_better=higher_is_better
    )
    return ComparisonResult(
        metric=metric,
        baseline_estimate=float(x.mean()) if n else float("nan"),
        candidate_estimate=float(y.mean()) if n else float("nan"),
        difference=float(diffs.mean()) if n else float("nan"),
        ci=ci,
        p_value=p_value,
        effect_size=cohen_d(x.tolist(), y.tolist()) if n >= 2 else None,
        effect_size_method="cohen_d" if n >= 2 else None,
        paired=True,
        n_baseline=n,
        n_candidate=n,
        conclusion=conclusion,
        rationale=rationale + (f" (n={n} pairs)" if n else " (no pairs)"),
    )


def proportion_comparison(
    metric: str,
    baseline: tuple[int, int],
    candidate: tuple[int, int],
    *,
    margin: float = 0.0,
    level: float = DEFAULT_LEVEL,
    higher_is_better: bool = True,
) -> ComparisonResult:
    """Unpaired comparison of two proportions (Newcombe/Wilson hybrid interval for the
    difference). Weaker than a paired comparison and flagged as such."""
    k1, n1 = baseline
    k2, n2 = candidate
    if n1 == 0 or n2 == 0:
        return ComparisonResult(
            metric=metric,
            baseline_estimate=float("nan"),
            candidate_estimate=float("nan"),
            difference=float("nan"),
            paired=False,
            n_baseline=n1,
            n_candidate=n2,
            conclusion=EvalStatus.INCONCLUSIVE,
            rationale="empty sample",
        )
    from evalkit.stats.intervals import wilson

    w1, w2 = wilson(k1, n1, level), wilson(k2, n2, level)
    p1, p2 = k1 / n1, k2 / n2
    diff = p2 - p1
    low = diff - math.sqrt((p2 - w2.low) ** 2 + (w1.high - p1) ** 2)
    high = diff + math.sqrt((w2.high - p2) ** 2 + (p1 - w1.low) ** 2)
    ci = IntervalResult(
        estimate=diff,
        low=low,
        high=high,
        level=level,
        method="newcombe_wilson",
        n=n1 + n2,
        assumptions=["two independent binomial samples"],
        warnings=["unpaired: weaker than a paired comparison"],
    )
    underpowered = min(n1, n2) < MIN_PAIRS
    conclusion, rationale = _conclude(
        ci, margin=margin, underpowered=underpowered, higher_is_better=higher_is_better
    )
    table = [[k1, n1 - k1], [k2, n2 - k2]]
    p_value = float(sps.fisher_exact(table)[1])
    return ComparisonResult(
        metric=metric,
        baseline_estimate=p1,
        candidate_estimate=p2,
        difference=diff,
        ci=ci,
        p_value=p_value,
        effect_size=cohen_h(p1, p2),
        effect_size_method="cohen_h",
        paired=False,
        n_baseline=n1,
        n_candidate=n2,
        conclusion=conclusion,
        rationale=rationale + f" (n={n1} vs {n2}, unpaired)",
    )
