"""STATISTICAL_ENGINE — Monte-Carlo, confidence intervals, paired comparisons, bootstrap.

Every method documents its assumptions in docs/STATISTICAL_METHODS.md. When assumptions fail
or data are insufficient, results are INCONCLUSIVE — never forced.
"""

from evalkit.stats.interfaces import ComparisonResult, IntervalResult, VarianceDecomposition

__all__ = ["ComparisonResult", "IntervalResult", "VarianceDecomposition"]
