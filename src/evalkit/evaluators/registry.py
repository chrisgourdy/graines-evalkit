"""Default evaluator registry."""

from __future__ import annotations

from evalkit.evaluators.deterministic import (
    ExactMatch,
    JsonSchemaCheck,
    MaxLength,
    NormalizedMatch,
    NumericTolerance,
    RegexCheck,
    RequiredKeys,
    TraceRules,
)
from evalkit.evaluators.interfaces import Evaluator


class DefaultEvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, Evaluator] = {}
        for cls in (
            ExactMatch,
            NormalizedMatch,
            JsonSchemaCheck,
            RegexCheck,
            RequiredKeys,
            NumericTolerance,
            MaxLength,
            TraceRules,
        ):
            self.register(cls())

    def get(self, evaluator_id: str) -> Evaluator:
        try:
            return self._evaluators[evaluator_id]
        except KeyError as exc:
            msg = f"unknown evaluator {evaluator_id!r}; known: {self.ids()}"
            raise KeyError(msg) from exc

    def register(self, evaluator: Evaluator) -> None:
        self._evaluators[evaluator.evaluator_id] = evaluator

    def ids(self) -> list[str]:
        return sorted(self._evaluators)
