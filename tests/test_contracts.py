"""Contract invariants: validation rules, round-trips, schema export."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from evalkit.contracts import (
    CONTRACT_SCHEMA_VERSION,
    Budget,
    BudgetScope,
    ControlState,
    Dimension,
    EvalStatus,
    EvaluationResult,
    MeasurementKind,
    Provenance,
    Scenario,
    UsageSource,
    VerificationSpec,
    export_json_schemas,
    new_id,
    utcnow,
)
from evalkit.contracts.usage import TokenUsage

NOW = datetime(2026, 10, 13, tzinfo=UTC)


def _scenario(**overrides: object) -> Scenario:
    base: dict[str, object] = {
        "scenario_id": "demo.greet.001",
        "version": "1.0.0",
        "project_id": "demo",
        "agent_id": "greeter",
        "name": "Greets by name",
        "description": "Agent must greet the user by name.",
        "objective": "Check basic instruction following.",
        "inputs": {"name": "Ada"},
        "expected_behavior": "Returns 'Hello Ada'.",
        "reference_outputs": {"text": "Hello Ada"},
        "verifications": [
            VerificationSpec(evaluator="exact_match", dimension=Dimension.ACCURACY, blocking=True)
        ],
        "provenance": Provenance(author="tests", created_at=NOW, origin="handwritten"),
    }
    base.update(overrides)
    return Scenario(**base)  # type: ignore[arg-type]


def test_scenario_roundtrip_and_version() -> None:
    s = _scenario()
    assert s.schema_version == CONTRACT_SCHEMA_VERSION
    again = Scenario.model_validate_json(s.model_dump_json())
    assert again == s


def test_scenario_rejects_bad_version_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _scenario(version="1.0")
    with pytest.raises(ValidationError):
        _scenario(unknown_field=1)


def test_scenario_requires_at_least_one_verification() -> None:
    with pytest.raises(ValidationError):
        _scenario(verifications=[])


def test_usage_estimated_requires_method() -> None:
    with pytest.raises(ValidationError):
        TokenUsage(provider="sim", model="m", source=UsageSource.ESTIMATED, input_tokens=1)
    ok = TokenUsage(
        provider="sim",
        model="m",
        source=UsageSource.ESTIMATED,
        input_tokens=10,
        output_tokens=5,
        estimation_method="chars/4",
    )
    assert ok.billable_total() == 15


def test_usage_unknown_has_no_figures() -> None:
    with pytest.raises(ValidationError):
        TokenUsage(provider="sim", model="m", source=UsageSource.UNKNOWN, total_tokens=3)
    u = TokenUsage(provider="sim", model="m", source=UsageSource.UNKNOWN)
    assert u.billable_total() is None


def test_billable_total_honours_declared_subsets() -> None:
    # cached input already inside input_tokens: must NOT be added again
    inside = TokenUsage(
        provider="anthropic",
        model="x",
        source=UsageSource.REPORTED,
        input_tokens=100,
        output_tokens=20,
        cached_input_tokens=60,
        subsets={"cached_input_tokens": "input_tokens"},
    )
    assert inside.billable_total() == 120
    # cached input reported separately: added once
    separate = TokenUsage(
        provider="other",
        model="x",
        source=UsageSource.REPORTED,
        input_tokens=40,
        output_tokens=20,
        cached_input_tokens=60,
    )
    assert separate.billable_total() == 120
    # provider total wins when present
    reported_total = TokenUsage(
        provider="other",
        model="x",
        source=UsageSource.REPORTED,
        input_tokens=40,
        output_tokens=20,
        total_tokens=61,
    )
    assert reported_total.billable_total() == 61


def test_evaluation_result_control_state_vs_conclusion() -> None:
    common = {
        "result_id": new_id("res"),
        "run_id": new_id("run"),
        "evaluator_id": "exact_match",
        "evaluator_version": "1.0.0",
        "dimension": Dimension.ACCURACY,
        "evaluated_at": utcnow(),
    }
    with pytest.raises(ValidationError):
        EvaluationResult(
            **common,
            control_state=ControlState.ERRORED,
            status=EvalStatus.PASS,
            measurement=MeasurementKind.OBJECTIVE,
        )
    with pytest.raises(ValidationError):
        EvaluationResult(
            **common,
            control_state=ControlState.COMPLETED,
            status=EvalStatus.NOT_EVALUATED,
            measurement=MeasurementKind.UNAVAILABLE,
            score=0.0,
        )
    ok = EvaluationResult(
        **common,
        control_state=ControlState.COMPLETED,
        status=EvalStatus.FAIL,
        measurement=MeasurementKind.OBJECTIVE,
        score=0.0,
    )
    assert ok.status is EvalStatus.FAIL


def test_budget_needs_a_cap_and_ordered_thresholds() -> None:
    with pytest.raises(ValidationError):
        Budget(budget_id="b", scope=BudgetScope.PROJECT, scope_ref="demo")
    with pytest.raises(ValidationError):
        Budget(
            budget_id="b",
            scope=BudgetScope.PROJECT,
            scope_ref="demo",
            max_cost=1.0,
            thresholds={"info": 0.9, "warning": 0.5},
        )
    b = Budget(budget_id="b", scope=BudgetScope.PROJECT, scope_ref="demo", max_tokens=1000)
    assert b.max_cost is None


def test_schema_export(tmp_path: Path) -> None:
    paths = export_json_schemas(tmp_path)
    names = {p.name for p in paths}
    assert "Scenario.schema.json" in names
    assert "TokenUsage.schema.json" in names
    schema = json.loads((tmp_path / "Scenario.schema.json").read_text())
    assert schema["$id"].endswith("Scenario.schema.json")
    assert "schema_version" in schema["properties"]
    assert schema.get("additionalProperties") is False
