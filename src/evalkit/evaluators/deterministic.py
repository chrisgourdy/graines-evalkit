"""Deterministic evaluators (family DETERMINISTIC / SCHEMA / REFERENCE / RULE / TRACE).

Each one returns a complete EvaluationResult. A negative conclusion is a normal return;
only evaluator faults raise (the engine records them as ERRORED / NOT_EVALUATED).
Common params: ``field`` — dotted path inside the run output (default: whole output).
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from evalkit.contracts import (
    ControlState,
    EvalStatus,
    EvaluationResult,
    Evidence,
    MeasurementKind,
    Run,
    Scenario,
    VerificationSpec,
    new_id,
    utcnow,
)
from evalkit.evaluators.interfaces import EvaluatorFamily


def _get_path(value: object, path: str | None) -> object:
    if not path:
        return value
    cur: Any = value
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else None
        else:
            return None
    return cur


def _num(value: object, default: float = 0.0) -> float:
    return float(value) if isinstance(value, int | float | str) else default


def _opt_int(value: object) -> int | None:
    return int(value) if isinstance(value, int | float | str) else None


def _strs(value: object) -> set[str]:
    return {str(v) for v in value} if isinstance(value, list | tuple | set) else set()


def _result(
    run: Run,
    spec: VerificationSpec,
    evaluator_id: str,
    version: str,
    *,
    passed: bool | None,
    message: str,
    evidence: list[Evidence] | None = None,
    score: float | None = None,
    value: float | None = None,
    unit: str | None = None,
) -> EvaluationResult:
    if passed is None:
        status, state, measurement = (
            EvalStatus.NOT_EVALUATED,
            ControlState.COMPLETED,
            MeasurementKind.UNAVAILABLE,
        )
        score = None
    else:
        status = EvalStatus.PASS if passed else EvalStatus.FAIL
        state, measurement = ControlState.COMPLETED, MeasurementKind.OBJECTIVE
        if score is None:
            score = 1.0 if passed else 0.0
    return EvaluationResult(
        result_id=new_id("res"),
        run_id=run.run_id,
        evaluator_id=evaluator_id,
        evaluator_version=version,
        dimension=spec.dimension,
        control_state=state,
        status=status,
        measurement=measurement,
        score=score,
        value=value,
        unit=unit,
        blocking=spec.blocking,
        message=message,
        evidence=evidence or [],
        evaluated_at=utcnow(),
    )


class _Base:
    evaluator_id = "base"
    evaluator_version = "1.0.0"
    family = EvaluatorFamily.DETERMINISTIC
    cost_bearing = False

    async def evaluate(
        self, run: Run, scenario: Scenario, spec: VerificationSpec
    ) -> EvaluationResult:
        if run.output is None:
            return _result(
                run,
                spec,
                self.evaluator_id,
                self.evaluator_version,
                passed=False,
                message="no output produced by the agent",
                evidence=[Evidence(kind="error", summary=run.error or "no output")],
            )
        return self.check(run, scenario, spec)

    def check(self, run: Run, scenario: Scenario, spec: VerificationSpec) -> EvaluationResult:
        raise NotImplementedError


class ExactMatch(_Base):
    """Output field equals reference field (deep equality)."""

    evaluator_id = "exact_match"
    family = EvaluatorFamily.REFERENCE

    def check(self, run: Run, scenario: Scenario, spec: VerificationSpec) -> EvaluationResult:
        field = spec.params.get("field")
        got = _get_path(run.output, str(field) if field else None)
        ref = _get_path(scenario.reference_outputs, str(field) if field else None)
        ok = got == ref
        return _result(
            run,
            spec,
            self.evaluator_id,
            self.evaluator_version,
            passed=ok,
            message="exact match" if ok else "output differs from reference",
            evidence=[]
            if ok
            else [
                Evidence(
                    kind="diff",
                    summary=f"expected={json.dumps(ref, default=str)[:200]} "
                    f"got={json.dumps(got, default=str)[:200]}",
                )
            ],
        )


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


class NormalizedMatch(_Base):
    """Case/punctuation/whitespace-insensitive string equality."""

    evaluator_id = "normalized_match"
    family = EvaluatorFamily.REFERENCE

    def check(self, run: Run, scenario: Scenario, spec: VerificationSpec) -> EvaluationResult:
        field = spec.params.get("field")
        got = _get_path(run.output, str(field) if field else None)
        ref = _get_path(scenario.reference_outputs, str(field) if field else None)
        if not isinstance(got, str) or not isinstance(ref, str):
            return _result(
                run,
                spec,
                self.evaluator_id,
                self.evaluator_version,
                passed=None,
                message="normalized_match needs string values on both sides",
            )
        ok = _normalize(got) == _normalize(ref)
        return _result(
            run,
            spec,
            self.evaluator_id,
            self.evaluator_version,
            passed=ok,
            message="normalized match" if ok else "normalized strings differ",
            evidence=[] if ok else [Evidence(kind="diff", summary=f"{ref!r} vs {got!r}")],
        )


class JsonSchemaCheck(_Base):
    """Output validates against ``params.schema`` (JSON Schema draft 2020-12)."""

    evaluator_id = "json_schema"
    family = EvaluatorFamily.SCHEMA

    def check(self, run: Run, scenario: Scenario, spec: VerificationSpec) -> EvaluationResult:
        import jsonschema

        schema = spec.params.get("schema")
        if not isinstance(schema, dict):
            msg = "json_schema needs params.schema (object)"
            raise ValueError(msg)
        field = spec.params.get("field")
        got = _get_path(run.output, str(field) if field else None)
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(got), key=lambda e: list(e.path))
        ok = not errors
        return _result(
            run,
            spec,
            self.evaluator_id,
            self.evaluator_version,
            passed=ok,
            message="schema valid" if ok else f"{len(errors)} schema error(s)",
            evidence=[Evidence(kind="schema_error", summary=e.message[:300]) for e in errors[:10]],
        )


class RegexCheck(_Base):
    """``params.pattern`` must match (``params.must_match=False`` inverts)."""

    evaluator_id = "regex"
    family = EvaluatorFamily.RULE

    def check(self, run: Run, scenario: Scenario, spec: VerificationSpec) -> EvaluationResult:
        pattern = spec.params.get("pattern")
        if not isinstance(pattern, str):
            msg = "regex needs params.pattern"
            raise ValueError(msg)
        field = spec.params.get("field")
        got = _get_path(run.output, str(field) if field else None)
        text = got if isinstance(got, str) else json.dumps(got, default=str)
        found = re.search(pattern, text, flags=re.MULTILINE) is not None
        must = bool(spec.params.get("must_match", True))
        ok = found == must
        return _result(
            run,
            spec,
            self.evaluator_id,
            self.evaluator_version,
            passed=ok,
            message=f"pattern {'found' if found else 'not found'} "
            f"({'required' if must else 'forbidden'})",
            evidence=[] if ok else [Evidence(kind="rule", summary=f"pattern={pattern!r}")],
        )


class RequiredKeys(_Base):
    """``params.keys`` must all be present (dotted paths) with non-null values."""

    evaluator_id = "required_keys"
    family = EvaluatorFamily.RULE

    def check(self, run: Run, scenario: Scenario, spec: VerificationSpec) -> EvaluationResult:
        keys = spec.params.get("keys")
        if not isinstance(keys, list):
            msg = "required_keys needs params.keys (list)"
            raise ValueError(msg)
        missing = [k for k in keys if _get_path(run.output, str(k)) is None]
        ok = not missing
        return _result(
            run,
            spec,
            self.evaluator_id,
            self.evaluator_version,
            passed=ok,
            message="all keys present" if ok else f"missing: {missing}",
            score=1 - len(missing) / max(1, len(keys)),
            evidence=[] if ok else [Evidence(kind="rule", summary=f"missing={missing}")],
        )


class NumericTolerance(_Base):
    """|got - ref| <= ``params.abs_tol`` or relative ``params.rel_tol``."""

    evaluator_id = "numeric_tolerance"
    family = EvaluatorFamily.REFERENCE

    def check(self, run: Run, scenario: Scenario, spec: VerificationSpec) -> EvaluationResult:
        field = spec.params.get("field")
        got = _get_path(run.output, str(field) if field else None)
        ref = _get_path(scenario.reference_outputs, str(field) if field else None)
        if not isinstance(got, int | float) or not isinstance(ref, int | float):
            return _result(
                run,
                spec,
                self.evaluator_id,
                self.evaluator_version,
                passed=None,
                message="numeric_tolerance needs numeric values on both sides",
            )
        abs_tol = _num(spec.params.get("abs_tol"))
        rel_tol = _num(spec.params.get("rel_tol"))
        diff = abs(float(got) - float(ref))
        ok = diff <= max(abs_tol, rel_tol * abs(float(ref)))
        return _result(
            run,
            spec,
            self.evaluator_id,
            self.evaluator_version,
            passed=ok,
            message=f"|diff|={diff:g}",
            value=diff,
            unit="abs_diff",
        )


class MaxLength(_Base):
    """Serialized output length <= ``params.max_chars``."""

    evaluator_id = "max_length"
    family = EvaluatorFamily.RULE

    def check(self, run: Run, scenario: Scenario, spec: VerificationSpec) -> EvaluationResult:
        max_chars = int(_num(spec.params.get("max_chars")))
        field = spec.params.get("field")
        got = _get_path(run.output, str(field) if field else None)
        text = got if isinstance(got, str) else json.dumps(got, default=str)
        ok = len(text) <= max_chars
        return _result(
            run,
            spec,
            self.evaluator_id,
            self.evaluator_version,
            passed=ok,
            message=f"{len(text)} chars (max {max_chars})",
            value=float(len(text)),
            unit="chars",
        )


class TraceRules(_Base):
    """Trajectory rules: ``forbidden_tools``, ``required_tools``, ``max_steps``, ``max_retries``."""

    evaluator_id = "trace_rules"
    family = EvaluatorFamily.TRACE

    async def evaluate(
        self, run: Run, scenario: Scenario, spec: VerificationSpec
    ) -> EvaluationResult:
        if run.trajectory is None:
            return _result(
                run,
                spec,
                self.evaluator_id,
                self.evaluator_version,
                passed=None,
                message="no trajectory reported by the adapter",
            )
        return self.check(run, scenario, spec)

    def check(self, run: Run, scenario: Scenario, spec: VerificationSpec) -> EvaluationResult:
        assert run.trajectory is not None
        steps = run.trajectory.steps
        tools = [s.tool_name for s in steps if s.tool_name]
        violations: list[str] = []
        forbidden = _strs(spec.params.get("forbidden_tools"))
        required = _strs(spec.params.get("required_tools"))
        used_forbidden = sorted(forbidden & set(tools))
        if used_forbidden:
            violations.append(f"forbidden tools used: {used_forbidden}")
        missing = sorted(required - set(tools))
        if missing:
            violations.append(f"required tools missing: {missing}")
        max_steps = _opt_int(spec.params.get("max_steps"))
        if max_steps is not None and len(steps) > max_steps:
            violations.append(f"{len(steps)} steps > max {max_steps}")
        max_retries = _opt_int(spec.params.get("max_retries"))
        retries = sum(1 for s in steps if s.kind.value == "retry")
        if max_retries is not None and retries > max_retries:
            violations.append(f"{retries} retries > max {max_retries}")
        ok = not violations
        return _result(
            run,
            spec,
            self.evaluator_id,
            self.evaluator_version,
            passed=ok,
            message="trace rules satisfied" if ok else "; ".join(violations),
            evidence=[Evidence(kind="trace", summary=v) for v in violations],
        )
