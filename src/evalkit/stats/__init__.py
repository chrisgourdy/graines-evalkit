"""STATISTICAL_ENGINE — Monte-Carlo, confidence intervals, paired comparisons, bootstrap.

Every method documents its assumptions in docs/STATISTICAL_METHODS.md. When assumptions fail
or data are insufficient, results are INCONCLUSIVE — never forced.
"""

from evalkit.stats.comparison import (
    MIN_PAIRS,
    cliffs_delta,
    cohen_d,
    cohen_h,
    holm,
    paired_comparison,
    proportion_comparison,
)
from evalkit.stats.interfaces import ComparisonResult, IntervalResult, VarianceDecomposition
from evalkit.stats.intervals import (
    MIN_N_MEAN_T,
    MIN_N_PROPORTION,
    bootstrap_bca,
    clopper_pearson,
    jeffreys,
    mean_interval,
    mean_t_interval,
    proportion_interval,
    rule_of_three,
    wilson,
)
from evalkit.stats.montecarlo import (
    dispersion,
    failure_rate,
    stratified_sample,
    variance_decomposition,
    worst_k,
)

__all__ = [
    "MIN_N_MEAN_T",
    "MIN_N_PROPORTION",
    "MIN_PAIRS",
    "ComparisonResult",
    "IntervalResult",
    "VarianceDecomposition",
    "bootstrap_bca",
    "cliffs_delta",
    "clopper_pearson",
    "cohen_d",
    "cohen_h",
    "dispersion",
    "failure_rate",
    "holm",
    "jeffreys",
    "mean_interval",
    "mean_t_interval",
    "paired_comparison",
    "proportion_comparison",
    "proportion_interval",
    "rule_of_three",
    "stratified_sample",
    "variance_decomposition",
    "wilson",
    "worst_k",
]
