"""Confidence intervals. Every function returns an IntervalResult carrying method, n,
assumptions and warnings. Minimum sample sizes are explicit; below them the interval is still
computed (it is honest, just wide) but flagged so callers conclude INCONCLUSIVE.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np
from scipy import stats as sps

from evalkit.stats.interfaces import IntervalResult

MIN_N_PROPORTION = 5
"""Below this, any proportion interval is flagged 'underpowered'."""
MIN_N_MEAN_T = 30
"""t-interval is only used at/above this n and without heavy tails; else bootstrap."""
DEFAULT_LEVEL = 0.95


def _check_counts(successes: int, n: int) -> None:
    if n < 0 or successes < 0 or successes > n:
        msg = f"invalid counts successes={successes} n={n}"
        raise ValueError(msg)


def wilson(successes: int, n: int, level: float = DEFAULT_LEVEL) -> IntervalResult:
    """Wilson score interval for a binomial proportion (default for pass rates)."""
    _check_counts(successes, n)
    warnings: list[str] = []
    if n == 0:
        return IntervalResult(
            estimate=float("nan"),
            low=0.0,
            high=1.0,
            level=level,
            method="wilson",
            n=0,
            assumptions=["binomial trials"],
            warnings=["n=0: no information"],
        )
    z = float(sps.norm.ppf(1 - (1 - level) / 2))
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    if n < MIN_N_PROPORTION:
        warnings.append(f"underpowered: n={n} < {MIN_N_PROPORTION}")
    if successes in (0, n):
        warnings.append("boundary estimate (0 or 1): consider clopper_pearson/rule_of_three")
    return IntervalResult(
        estimate=p,
        low=max(0.0, centre - half),
        high=min(1.0, centre + half),
        level=level,
        method="wilson",
        n=n,
        assumptions=["binomial, independent trials at the chosen sampling unit"],
        warnings=warnings,
    )


def clopper_pearson(successes: int, n: int, level: float = DEFAULT_LEVEL) -> IntervalResult:
    """Exact (conservative) interval; preferred near 0/1 or for very small n."""
    _check_counts(successes, n)
    if n == 0:
        return wilson(0, 0, level)
    alpha = 1 - level
    low = 0.0 if successes == 0 else float(sps.beta.ppf(alpha / 2, successes, n - successes + 1))
    high = (
        1.0 if successes == n else float(sps.beta.ppf(1 - alpha / 2, successes + 1, n - successes))
    )
    return IntervalResult(
        estimate=successes / n,
        low=low,
        high=high,
        level=level,
        method="clopper_pearson",
        n=n,
        assumptions=["binomial, independent trials"],
        warnings=[f"underpowered: n={n} < {MIN_N_PROPORTION}"] if n < MIN_N_PROPORTION else [],
    )


def jeffreys(successes: int, n: int, level: float = DEFAULT_LEVEL) -> IntervalResult:
    """Jeffreys (Beta(1/2,1/2) posterior) interval; good behaviour for rare events."""
    _check_counts(successes, n)
    if n == 0:
        return wilson(0, 0, level)
    alpha = 1 - level
    a, b = successes + 0.5, n - successes + 0.5
    low = 0.0 if successes == 0 else float(sps.beta.ppf(alpha / 2, a, b))
    high = 1.0 if successes == n else float(sps.beta.ppf(1 - alpha / 2, a, b))
    return IntervalResult(
        estimate=successes / n,
        low=low,
        high=high,
        level=level,
        method="jeffreys",
        n=n,
        assumptions=["binomial; Jeffreys prior"],
    )


def rule_of_three(n: int, level: float = DEFAULT_LEVEL) -> IntervalResult:
    """Upper bound on a rate when 0 events were observed in n trials (≈ 3/n at 95 %)."""
    if n <= 0:
        msg = "n must be > 0"
        raise ValueError(msg)
    high = 1 - (1 - level) ** (1 / n)
    return IntervalResult(
        estimate=0.0,
        low=0.0,
        high=high,
        level=level,
        method="rule_of_three",
        n=n,
        assumptions=["0 events observed; one-sided upper bound"],
        warnings=["point estimate 0 is not evidence of impossibility"],
    )


def proportion_interval(successes: int, n: int, level: float = DEFAULT_LEVEL) -> IntervalResult:
    """Automatic choice: Clopper-Pearson for n < MIN_N_PROPORTION or boundary counts,
    Wilson otherwise (docs/STATISTICAL_METHODS.md §3)."""
    _check_counts(successes, n)
    if n == 0:
        return wilson(0, 0, level)
    if n < MIN_N_PROPORTION or successes in (0, n):
        return clopper_pearson(successes, n, level)
    return wilson(successes, n, level)


def _skewness(values: np.ndarray) -> float:
    if len(values) < 3 or float(np.std(values)) == 0.0:
        return 0.0
    return float(sps.skew(values))


def mean_t_interval(values: Sequence[float], level: float = DEFAULT_LEVEL) -> IntervalResult:
    """t-interval for a mean. Flags n < MIN_N_MEAN_T and heavy skew (CLT conditions)."""
    arr = np.asarray(list(values), dtype=float)
    n = int(arr.size)
    warnings: list[str] = []
    if n < 2:
        return IntervalResult(
            estimate=float(arr.mean()) if n else float("nan"),
            low=float("nan"),
            high=float("nan"),
            level=level,
            method="t",
            n=n,
            assumptions=["CLT"],
            warnings=["n<2: no interval"],
        )
    mean = float(arr.mean())
    sem = float(arr.std(ddof=1) / math.sqrt(n))
    tcrit = float(sps.t.ppf(1 - (1 - level) / 2, df=n - 1))
    if n < MIN_N_MEAN_T:
        warnings.append(f"n={n} < {MIN_N_MEAN_T}: CLT approximation weak, prefer bootstrap")
    skew = _skewness(arr)
    if abs(skew) > 1.0:
        warnings.append(f"skewness {skew:.2f}: heavy tail, prefer bootstrap")
    return IntervalResult(
        estimate=mean,
        low=mean - tcrit * sem,
        high=mean + tcrit * sem,
        level=level,
        method="t",
        n=n,
        assumptions=["approximately normal sampling distribution of the mean (CLT)"],
        warnings=warnings,
    )


def bootstrap_bca(
    values: Sequence[float],
    statistic: Callable[[np.ndarray], float] = lambda a: float(np.mean(a)),
    *,
    level: float = DEFAULT_LEVEL,
    n_resamples: int = 2000,
    seed: int | None = 0,
) -> IntervalResult:
    """Bias-corrected and accelerated bootstrap (seeded, deterministic)."""
    arr = np.asarray(list(values), dtype=float)
    n = int(arr.size)
    if n < 2:
        return IntervalResult(
            estimate=float(statistic(arr)) if n else float("nan"),
            low=float("nan"),
            high=float("nan"),
            level=level,
            method="bootstrap_bca",
            n=n,
            warnings=["n<2: no interval"],
        )
    rng = np.random.default_rng(seed)
    theta = float(statistic(arr))
    idx = rng.integers(0, n, size=(n_resamples, n))
    boots = np.array([statistic(arr[row]) for row in idx], dtype=float)
    if float(np.std(boots)) == 0.0:
        return IntervalResult(
            estimate=theta,
            low=theta,
            high=theta,
            level=level,
            method="bootstrap_bca",
            n=n,
            warnings=["degenerate bootstrap distribution (constant data)"],
        )
    # bias correction
    prop = float(np.mean(boots < theta))
    prop = min(max(prop, 1e-9), 1 - 1e-9)
    z0 = float(sps.norm.ppf(prop))
    # acceleration via jackknife
    jack = np.array([statistic(np.delete(arr, i)) for i in range(n)], dtype=float)
    jm = jack.mean()
    num = float(np.sum((jm - jack) ** 3))
    den = 6.0 * float(np.sum((jm - jack) ** 2)) ** 1.5
    a = num / den if den != 0 else 0.0
    alpha = 1 - level
    zl, zh = float(sps.norm.ppf(alpha / 2)), float(sps.norm.ppf(1 - alpha / 2))

    def adj(z: float) -> float:
        return float(sps.norm.cdf(z0 + (z0 + z) / (1 - a * (z0 + z))))

    lo_q, hi_q = adj(zl), adj(zh)
    low, high = float(np.quantile(boots, lo_q)), float(np.quantile(boots, hi_q))
    warnings = [f"underpowered: n={n} < 10"] if n < 10 else []
    return IntervalResult(
        estimate=theta,
        low=low,
        high=high,
        level=level,
        method="bootstrap_bca",
        n=n,
        assumptions=[f"i.i.d. sample at the chosen unit; n_resamples={n_resamples}"],
        warnings=warnings,
    )


def mean_interval(
    values: Sequence[float], level: float = DEFAULT_LEVEL, seed: int = 0
) -> IntervalResult:
    """Automatic choice: t when n ≥ MIN_N_MEAN_T and |skew| ≤ 1, else BCa bootstrap."""
    arr = np.asarray(list(values), dtype=float)
    if arr.size >= MIN_N_MEAN_T and abs(_skewness(arr)) <= 1.0:
        return mean_t_interval(arr.tolist(), level)
    return bootstrap_bca(arr.tolist(), level=level, seed=seed)
