"""IMPROVEMENT — retrofit cycle.

OBSERVE > CLASSIFY > DIAGNOSE > PRIORITIZE > PROPOSE > ISOLATE > TEST > COMPARE > DECIDE > RECORD
> LEARN. Learning = verified, provenance-tracked knowledge base (docs/LEARNINGS.md), never
weight training.
"""

from evalkit.improvement.apply import (
    AppliedFix,
    ApplyRefusedError,
    apply_fix,
    get_experiment,
    list_backups,
    rollback,
)
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
    "AppliedFix",
    "ApplyRefusedError",
    "LearningStore",
    "RetrofitCycle",
    "RetrofitResult",
    "apply_fix",
    "get_experiment",
    "list_backups",
    "params_override",
    "revert_to_last_good",
    "rollback",
    "self_evaluate",
]
