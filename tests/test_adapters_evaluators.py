"""Simulated adapters and deterministic evaluators (no provider)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from evalkit.adapters import adapter_ids, create_adapter
from evalkit.adapters.sim import DeterministicSimAdapter, StochasticSimAdapter
from evalkit.contracts import (
    ControlState,
    Dimension,
    EvalStatus,
    MeasurementKind,
    Provenance,
    Run,
    RunStatus,
    Scenario,
    Trajectory,
    TrajectoryStep,
    UsageSource,
    VerificationSpec,
    new_id,
    utcnow,
)
from evalkit.evaluators import DefaultEvaluatorRegistry

NOW = datetime(2026, 10, 14, tzinfo=UTC)


def scenario(reference: dict[str, object], **kw: object) -> Scenario:
    return Scenario(
        scenario_id="tst.s.001",
        version="1.0.0",
        project_id="tst",
        agent_id="agt",
        name="n",
        description="d",
        objective="o",
        inputs={"q": "x"},
        expected_behavior="e",
        reference_outputs=reference,
        verifications=[VerificationSpec(evaluator="exact_match", dimension=Dimension.ACCURACY)],
        provenance=Provenance(author="t", created_at=NOW, origin="test"),
        **kw,  # type: ignore[arg-type]
    )


def run_with(output: object, trajectory: Trajectory | None = None) -> Run:
    return Run(
        run_id=new_id("run"),
        campaign_id="c",
        scenario_id="tst.s.001",
        scenario_version="1.0.0",
        project_id="tst",
        agent_id="agt",
        agent_version="1",
        attempt=1,
        status=RunStatus.COMPLETED,
        output=output,
        trajectory=trajectory,
    )


def ev(
    evaluator: str, dimension: Dimension = Dimension.ACCURACY, **params: object
) -> VerificationSpec:
    return VerificationSpec(evaluator=evaluator, dimension=dimension, params=params)


REG = DefaultEvaluatorRegistry()


def evaluate(spec: VerificationSpec, run: Run, scn: Scenario):  # type: ignore[no-untyped-def]
    return asyncio.run(REG.get(spec.evaluator).evaluate(run, scn, spec))


# ------------------------------------------------------------------- adapters


def test_registry_lists_reference_adapters() -> None:
    assert {"sim.deterministic", "sim.stochastic", "python.callable"} <= set(adapter_ids())
    with pytest.raises(KeyError):
        create_adapter("nope", "1", {})


def test_deterministic_reference_and_wrong() -> None:
    scn = scenario({"text": "Hello", "n": 1, "ok": True})
    good = DeterministicSimAdapter("1", {"behavior": "reference"})
    bad = DeterministicSimAdapter("1", {"behavior": "wrong"})
    r1 = asyncio.run(good.invoke(scn, seed=None, timeout_s=None))
    r2 = asyncio.run(bad.invoke(scn, seed=None, timeout_s=None))
    assert r1.output == scn.reference_outputs
    assert r2.output == {"text": "Hello (wrong)", "n": 2, "ok": False}
    assert r1.usage[0].source is UsageSource.REPORTED
    assert r1.usage[0].billable_total() == r1.usage[0].total_tokens


def test_deterministic_unknown_usage_when_not_reporting() -> None:
    a = DeterministicSimAdapter("1", {"report_usage": False})
    r = asyncio.run(a.invoke(scenario({"t": "x"}), seed=None, timeout_s=None))
    assert r.usage[0].source is UsageSource.UNKNOWN
    assert r.usage[0].billable_total() is None
    assert a.capabilities.reports_usage is False


def test_deterministic_error_behavior() -> None:
    a = DeterministicSimAdapter("1", {"behavior": "error"})
    r = asyncio.run(a.invoke(scenario({"t": "x"}), seed=None, timeout_s=None))
    assert r.output is None and "error" in r.metadata


def test_stochastic_is_seed_reproducible_and_varies() -> None:
    a = StochasticSimAdapter("1", {"p_wrong": 0.5, "p_error": 0.1, "p_retry": 0.3})
    scn = scenario({"t": "x"})
    outs = [asyncio.run(a.invoke(scn, seed=s, timeout_s=None)).output for s in range(40)]
    again = [asyncio.run(a.invoke(scn, seed=s, timeout_s=None)).output for s in range(40)]
    assert outs == again
    assert len({str(o) for o in outs}) > 1
    assert a.capabilities.deterministic is False and a.capabilities.supports_seed


def test_stochastic_emits_retry_and_error_steps() -> None:
    a = StochasticSimAdapter("1", {"p_wrong": 0.0, "p_error": 1.0, "p_retry": 1.0})
    r = asyncio.run(a.invoke(scenario({"t": "x"}), seed=1, timeout_s=None))
    kinds = [s["kind"] for s in r.trajectory_steps]  # type: ignore[index]
    assert kinds == ["error", "retry", "error"]
    assert r.output is None


def test_callable_adapter_wraps_function_and_errors() -> None:
    def fn(inputs: dict[str, object], context: dict[str, object]) -> object:
        if inputs.get("q") == "boom":
            raise ValueError("bad input")
        return {"echo": inputs["q"]}

    a = create_adapter("python.callable", "1", {"fn": fn})
    ok = asyncio.run(a.invoke(scenario({"echo": "x"}), seed=None, timeout_s=None))
    assert ok.output == {"echo": "x"} and ok.usage[0].source is UsageSource.UNKNOWN
    scn = scenario({"echo": "x"})
    scn = scn.model_copy(update={"inputs": {"q": "boom"}})
    err = asyncio.run(a.invoke(scn, seed=None, timeout_s=None))
    assert err.output is None and "ValueError" in str(err.metadata["error"])


# ----------------------------------------------------------------- evaluators


def test_exact_and_normalized_match() -> None:
    scn = scenario({"text": "Hello, Ada!"})
    assert (
        evaluate(ev("exact_match", field="text"), run_with({"text": "Hello, Ada!"}), scn).status
        is EvalStatus.PASS
    )
    bad = evaluate(ev("exact_match", field="text"), run_with({"text": "hello ada"}), scn)
    assert bad.status is EvalStatus.FAIL and bad.evidence[0].kind == "diff"
    assert (
        evaluate(ev("normalized_match", field="text"), run_with({"text": "hello ada"}), scn).status
        is EvalStatus.PASS
    )
    na = evaluate(ev("normalized_match", field="text"), run_with({"text": 3}), scn)
    assert na.status is EvalStatus.NOT_EVALUATED and na.measurement is MeasurementKind.UNAVAILABLE


def test_json_schema_regex_required_keys() -> None:
    scn = scenario({})
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}
    assert (
        evaluate(ev("json_schema", Dimension.FORMAT, schema=schema), run_with({"a": 1}), scn).status
        is EvalStatus.PASS
    )
    bad = evaluate(ev("json_schema", Dimension.FORMAT, schema=schema), run_with({"a": "x"}), scn)
    assert bad.status is EvalStatus.FAIL and bad.evidence
    assert (
        evaluate(
            ev("regex", Dimension.COMPLIANCE, pattern=r"^Hello"), run_with("Hello you"), scn
        ).status
        is EvalStatus.PASS
    )
    assert (
        evaluate(
            ev("regex", Dimension.SECURITY, pattern="password", must_match=False),
            run_with("my password"),
            scn,
        ).status
        is EvalStatus.FAIL
    )
    rk = evaluate(
        ev("required_keys", Dimension.COMPLETENESS, keys=["a", "b.c"]),
        run_with({"a": 1, "b": {}}),
        scn,
    )
    assert rk.status is EvalStatus.FAIL and rk.score == 0.5


def test_numeric_tolerance_and_max_length() -> None:
    scn = scenario({"v": 10.0})
    assert (
        evaluate(ev("numeric_tolerance", field="v", abs_tol=0.5), run_with({"v": 10.4}), scn).status
        is EvalStatus.PASS
    )
    assert (
        evaluate(
            ev("numeric_tolerance", field="v", rel_tol=0.01), run_with({"v": 10.4}), scn
        ).status
        is EvalStatus.FAIL
    )
    assert (
        evaluate(ev("numeric_tolerance", field="v"), run_with({"v": "ten"}), scn).status
        is EvalStatus.NOT_EVALUATED
    )
    ml = evaluate(ev("max_length", Dimension.CONSTRAINTS, max_chars=3), run_with("abcd"), scn)
    assert ml.status is EvalStatus.FAIL and ml.value == 4


def test_trace_rules() -> None:
    now = utcnow()
    steps = [
        TrajectoryStep(index=0, kind="llm_call", state="s", action="generate", started_at=now),  # type: ignore[arg-type]
        TrajectoryStep(
            index=1,
            kind="tool_call",
            state="s",
            action="send_email",
            tool_name="send_email",
            started_at=now,
        ),  # type: ignore[arg-type]
        TrajectoryStep(
            index=2, kind="retry", state="s", action="generate", retry_of=0, started_at=now
        ),  # type: ignore[arg-type]
    ]
    run = run_with({"x": 1}, Trajectory(run_id="r", steps=steps))
    scn = scenario({})
    res = evaluate(
        ev(
            "trace_rules",
            Dimension.TOOL_USE,
            forbidden_tools=["send_email"],
            required_tools=["lookup"],
            max_steps=2,
            max_retries=0,
        ),
        run,
        scn,
    )
    assert res.status is EvalStatus.FAIL and len(res.evidence) == 4
    assert (
        evaluate(
            ev("trace_rules", Dimension.TOOL_USE, required_tools=["send_email"]), run, scn
        ).status
        is EvalStatus.PASS
    )
    assert (
        evaluate(ev("trace_rules", Dimension.TOOL_USE), run_with({"x": 1}), scn).status
        is EvalStatus.NOT_EVALUATED
    )


def test_no_output_fails_but_control_completed() -> None:
    res = evaluate(ev("exact_match"), run_with(None), scenario({"t": 1}))
    assert res.status is EvalStatus.FAIL and res.control_state is ControlState.COMPLETED


def test_evaluator_param_fault_raises() -> None:
    with pytest.raises(ValueError, match=r"params\.schema"):
        evaluate(ev("json_schema", Dimension.FORMAT), run_with({}), scenario({}))


def test_injection_guard_flags_markers_and_passes_clean_output() -> None:
    import asyncio

    from evalkit.adapters.sim import INJECTION_TEXT, _inject
    from evalkit.contracts import Dimension, EvalStatus, Run, RunStatus, VerificationSpec, utcnow
    from evalkit.evaluators import DefaultEvaluatorRegistry

    guard = DefaultEvaluatorRegistry().get("injection_guard")
    spec = VerificationSpec(evaluator="injection_guard", dimension=Dimension.SECURITY)

    def run_with(output: object) -> Run:
        return Run(
            run_id="run_x",
            campaign_id="cmp_x",
            scenario_id="demo.guarded.sec.001",
            scenario_version="1.0.0",
            project_id="demo",
            agent_id="greeter-guarded",
            agent_version="1.0.0",
            attempt=1,
            status=RunStatus.COMPLETED,
            started_at=utcnow(),
            output=output,
        )

    sc = scenario({"text": "Hello Ada"})
    clean = asyncio.run(guard.evaluate(run_with({"text": "Hello Ada"}), sc, spec))
    assert clean.status is EvalStatus.PASS and clean.value == 0
    dirty = asyncio.run(guard.evaluate(run_with(_inject({"text": "Hello Ada"})), sc, spec))
    assert dirty.status is EvalStatus.FAIL and dirty.value and dirty.value >= 2
    assert all(e.kind == "injection_marker" for e in dirty.evidence)
    assert "IGNORE ALL PREVIOUS" in INJECTION_TEXT
    custom = VerificationSpec(
        evaluator="injection_guard",
        dimension=Dimension.SECURITY,
        params={"patterns": [r"secret\s+handshake"]},
    )
    hit = asyncio.run(guard.evaluate(run_with("the secret handshake is"), sc, custom))
    assert hit.status is EvalStatus.FAIL
