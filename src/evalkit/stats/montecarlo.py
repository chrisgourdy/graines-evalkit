"""Monte-Carlo helpers: seeded scenario sampling, dispersion, failure rates, tails,
variance decomposition. Nothing here assumes independence across repetitions of one scenario:
the sampling unit is explicit in every output."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import numpy as np

from evalkit.stats.interfaces import IntervalResult, VarianceDecomposition
from evalkit.stats.intervals import DEFAULT_LEVEL, proportion_interval


def stratified_sample(
    items: Sequence[Any],
    strata: Sequence[str],
    fraction: float,
    *,
    seed: int,
    minimum_per_stratum: int = 1,
) -> list[Any]:
    """Seeded stratified sampling (e.g. scenarios by criticality). Each stratum keeps at least
    ``minimum_per_stratum`` items when available, so rare critical strata are never dropped."""
    if len(items) != len(strata):
        msg = "items and strata must align"
        raise ValueError(msg)
    rng = np.random.default_rng(seed)
    groups: dict[str, list[int]] = defaultdict(list)
    for i, s in enumerate(strata):
        groups[s].append(i)
    chosen: list[int] = []
    for key in sorted(groups):
        idx = groups[key]
        k = max(min(minimum_per_stratum, len(idx)), round(len(idx) * fraction))
        picked = rng.choice(idx, size=min(k, len(idx)), replace=False)
        chosen.extend(int(p) for p in picked)
    return [items[i] for i in sorted(chosen)]


def dispersion(values: Sequence[float]) -> dict[str, float | None]:
    arr = np.asarray(list(values), float)
    if arr.size == 0:
        return {
            "n": 0,
            "mean": None,
            "std": None,
            "cv": None,
            "p50": None,
            "p95": None,
            "min": None,
            "max": None,
        }
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
    return {
        "n": int(arr.size),
        "mean": mean,
        "std": std,
        "cv": (std / mean) if mean else None,
        "p50": float(np.quantile(arr, 0.5)),
        "p95": float(np.quantile(arr, 0.95)),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def failure_rate(failures: int, n: int, level: float = DEFAULT_LEVEL) -> IntervalResult:
    """Failure frequency with an honest interval (rule of three when 0 failures)."""
    from evalkit.stats.intervals import rule_of_three

    if n > 0 and failures == 0:
        return rule_of_three(n, level)
    return proportion_interval(failures, n, level)


def worst_k(
    values: Sequence[tuple[str, float]], k: int = 5, *, lower_is_worse: bool = True
) -> list[tuple[str, float]]:
    """Tail analysis: the k worst (label, value) pairs."""
    return sorted(values, key=lambda t: t[1], reverse=not lower_is_worse)[:k]


def variance_decomposition(groups: dict[str, Sequence[float]]) -> VarianceDecomposition:
    """One-way decomposition: between-scenario vs within-scenario (generation) variance of a
    per-run metric. Descriptive (method-of-moments), not a test."""
    arrays = {k: np.asarray(list(v), float) for k, v in groups.items() if len(v) > 0}
    if len(arrays) < 2:
        return VarianceDecomposition(method="one_way_moments", note="needs ≥2 scenarios")
    all_vals = np.concatenate(list(arrays.values()))
    grand = float(all_vals.mean())
    within = [float(a.var(ddof=1)) for a in arrays.values() if a.size > 1]
    within_var = float(np.mean(within)) if within else None
    between_var = float(np.mean([(a.mean() - grand) ** 2 for a in arrays.values()]))
    return VarianceDecomposition(
        between_generations=within_var,
        between_scenarios=between_var,
        method="one_way_moments",
        note=(
            "between_generations = mean within-scenario variance (needs repetitions); "
            "between_scenarios = variance of scenario means around the grand mean"
        ),
    )
