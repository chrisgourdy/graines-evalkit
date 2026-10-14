"""IMPROVEMENT — retrofit cycle.

OBSERVE > CLASSIFY > DIAGNOSE > PRIORITIZE > PROPOSE > ISOLATE > TEST > COMPARE > DECIDE > RECORD
> LEARN. Learning = verified, provenance-tracked knowledge base (docs/LEARNINGS.md), never
weight training.
"""

from evalkit.improvement.learnings import STATUSES, LearningStore
from evalkit.improvement.retrofit import (
    RetrofitCycle,
    RetrofitResult,
    params_override,
    revert_to_last_good,
)
from evalkit.improvement.self_eval import CHECKS, self_evaluate

__all__ = [
    "CHECKS",
    "STATUSES",
    "LearningStore",
    "RetrofitCycle",
    "RetrofitResult",
    "params_override",
    "revert_to_last_good",
    "self_evaluate",
]
