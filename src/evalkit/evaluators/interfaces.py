"""Evaluator port. Deterministic, schema, reference, rule, trace, LLM-assisted, human, composite."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from evalkit.contracts import EvaluationResult, Run, Scenario, VerificationSpec


class EvaluatorFamily(StrEnum):
    DETERMINISTIC = "deterministic"
    SCHEMA = "schema"
    REFERENCE = "reference"
    RULE = "rule"
    TRACE = "trace"
    LLM = "llm"
    HUMAN = "human"
    COMPOSITE = "composite"


@runtime_checkable
class Evaluator(Protocol):
    evaluator_id: str
    evaluator_version: str
    family: EvaluatorFamily
    cost_bearing: bool

    async def evaluate(
        self, run: Run, scenario: Scenario, spec: VerificationSpec
    ) -> EvaluationResult:
        """Never raise for a negative conclusion; raise only for evaluator faults
        (the engine converts those into control_state=ERRORED / status=NOT_EVALUATED).
        """
        ...


class EvaluatorRegistry(Protocol):
    def get(self, evaluator_id: str) -> Evaluator: ...
    def register(self, evaluator: Evaluator) -> None: ...
    def ids(self) -> list[str]: ...
