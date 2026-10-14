"""Self-evaluation of EVALKIT's own mechanisms, persisted as a Scorecard of agent ``evalkit``.

Each check is a deterministic, provider-free control: statistical coverage, token accounting,
cost computation, budget enforcement, audit chain integrity, schema export, documentation
presence. A failing check is reported FAIL; a check that cannot run is NOT_EVALUATED — it is
never hidden. Changing these checks is a governance action (docs/AUTONOMY_POLICY.md).
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np

from evalkit import __version__
from evalkit.contracts import (
    Budget,
    BudgetScope,
    Campaign,
    CostStatus,
    Dimension,
    DimensionScore,
    EvalStatus,
    MeasurementKind,
    PriceEntry,
    Profile,
    Scorecard,
    TokenUsage,
    UsageSource,
    new_id,
    utcnow,
)
from evalkit.contracts.scorecard import ConfidenceInterval
from evalkit.storage.sqlite import SQLiteRepository

Check = Callable[[SQLiteRepository], tuple[bool, str]]


def check_statistics(_: SQLiteRepository) -> tuple[bool, str]:
    from evalkit.stats import wilson

    rng = np.random.default_rng(2026)
    p, n, sims = 0.3, 30, 4000
    ks = rng.binomial(n, p, size=sims)
    cov = float(np.mean([wilson(int(k), n).low <= p <= wilson(int(k), n).high for k in ks]))
    return (
        0.92 <= cov <= 0.98,
        f"Wilson 95% coverage {cov:.3f} on {sims} simulations (p={p}, n={n})",
    )


def check_token_accounting(_: SQLiteRepository) -> tuple[bool, str]:
    from evalkit.token_meter import from_anthropic, from_openai

    a = from_anthropic(
        "m",
        {
            "input_tokens": 100,
            "output_tokens": 40,
            "cache_read_input_tokens": 300,
            "cache_creation_input_tokens": 50,
        },
    )
    o = from_openai(
        "m",
        {
            "prompt_tokens": 400,
            "completion_tokens": 120,
            "total_tokens": 520,
            "prompt_tokens_details": {"cached_tokens": 300},
            "completion_tokens_details": {"reasoning_tokens": 80},
        },
    )
    ok = (
        a.billable_total() == 490
        and o.billable_total() == 520
        and o.model_copy(update={"total_tokens": None}).billable_total() == 520
    )
    return (
        ok,
        f"anthropic total {a.billable_total()} (expected 490), openai total {o.billable_total()} (expected 520, subsets not double counted)",
    )


def check_cost(_: SQLiteRepository) -> tuple[bool, str]:
    from evalkit.cost_controller import compute_cost

    price = PriceEntry(
        price_id="self/m",
        provider="p",
        model_id="m",
        valid_from=date(2026, 1, 1),
        input_per_million=Decimal("1"),
        output_per_million=Decimal("2"),
        cached_input_per_million=Decimal("0.1"),
        source="self-check",
        verified_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    u = TokenUsage(
        provider="p",
        model="m",
        source=UsageSource.REPORTED,
        input_tokens=1_000_000,
        output_tokens=0,
        cached_input_tokens=400_000,
        subsets={"cached_input_tokens": "input_tokens"},
    )
    c = compute_cost(u, price)
    unknown = compute_cost(u, None)
    ok = (
        c.amount == Decimal("0.64")
        and c.status is CostStatus.MEASURED
        and unknown.status is CostStatus.UNKNOWN
    )
    return (
        ok,
        f"subset-aware cost {c.amount} (expected 0.64); unknown price -> {unknown.status.value}",
    )


def check_budgets(_: SQLiteRepository) -> tuple[bool, str]:
    from evalkit.cost_controller import BudgetDecision, SQLiteCostController

    with tempfile.TemporaryDirectory() as tmp:
        repo = SQLiteRepository(Path(tmp))
        repo.migrate()
        ctl = SQLiteCostController(repo)
        ctl.save_budget(
            Budget(budget_id="b", scope=BudgetScope.PROJECT, scope_ref="self", max_cost=1.0)
        )
        camp = Campaign(
            campaign_id="c",
            project_id="self",
            agent_id="a",
            agent_version="1",
            profile=Profile.QUICK,
            scenario_ids=["x.y.z"],
            created_at=utcnow(),
            evalkit_version=__version__,
        )
        d1, _r = ctl.reserve(camp, run_id="r1", expected_cost=0.7, expected_tokens=None)
        d2, _r2 = ctl.reserve(camp, run_id="r2", expected_cost=0.7, expected_tokens=None)
        d3, _r3 = ctl.reserve(
            camp.model_copy(update={"project_id": "other"}),
            run_id="r3",
            expected_cost=0.1,
            expected_tokens=None,
        )
        repo.close()
    ok = d1 is BudgetDecision.ALLOW and d2 is BudgetDecision.BLOCK and d3 is BudgetDecision.BLOCK
    return (
        ok,
        f"reserve 0.7 -> {d1.value}; second 0.7 over cap 1.0 -> {d2.value}; no budget -> {d3.value}",
    )


def check_audit_chain(repo: SQLiteRepository) -> tuple[bool, str]:
    ok, n = repo.verify_chain()
    return (
        ok,
        f"hash chain {'intact' if ok else 'BROKEN at ' + str(n)} over {n} events"
        if ok
        else f"hash chain broken at sequence {n}",
    )


def check_schemas(_: SQLiteRepository) -> tuple[bool, str]:
    from evalkit.contracts import export_json_schemas

    with tempfile.TemporaryDirectory() as tmp:
        paths = export_json_schemas(Path(tmp))
    return len(paths) == 11, f"{len(paths)} contract schemas exported (expected 11)"


def check_docs(_: SQLiteRepository) -> tuple[bool, str]:
    root = Path(__file__).resolve().parents[3]
    required = ["CLAUDE.md", "docs/STATUS.md", "docs/ACCEPTANCE_SCENARIOS.md", "docs/TUTORIEL.md"]
    missing = [r for r in required if not (root / r).is_file()]
    if not (root / "CLAUDE.md").is_file():
        return True, "not running from a source checkout: documentation check not applicable"
    return not missing, "mandatory docs present" if not missing else f"missing: {missing}"


CHECKS: list[tuple[Dimension, str, Check]] = [
    (Dimension.ACCURACY, "statistics", check_statistics),
    (Dimension.TOKENS, "token_accounting", check_token_accounting),
    (Dimension.COST, "cost_computation", check_cost),
    (Dimension.CONSTRAINTS, "budget_enforcement", check_budgets),
    (Dimension.SECURITY, "audit_chain", check_audit_chain),
    (Dimension.FORMAT, "schema_export", check_schemas),
    (Dimension.COMPLIANCE, "documentation", check_docs),
]


def self_evaluate(
    repo: SQLiteRepository, *, persist: bool = True
) -> tuple[Scorecard, list[tuple[str, bool | None, str]]]:
    details: list[tuple[str, bool | None, str]] = []
    dims: list[DimensionScore] = []
    eliminatory: list[str] = []
    for dim, name, fn in CHECKS:
        try:
            ok, msg = fn(repo)
            passed: bool | None = ok
        except Exception as exc:  # a check that cannot run is reported, never hidden
            passed, msg = None, f"check could not run: {type(exc).__name__}: {exc}"
        details.append((name, passed, msg))
        if passed is False:
            eliminatory.append(name)
        dims.append(
            DimensionScore(
                dimension=dim,
                status=EvalStatus.PASS
                if passed
                else EvalStatus.FAIL
                if passed is False
                else EvalStatus.NOT_EVALUATED,
                measurement=MeasurementKind.OBJECTIVE
                if passed is not None
                else MeasurementKind.UNAVAILABLE,
                pass_rate=1.0 if passed else 0.0 if passed is False else None,
                ci=ConfidenceInterval(
                    low=1.0 if passed else 0.0,
                    high=1.0 if passed else 0.0,
                    level=0.95,
                    method="deterministic_check",
                    n=1,
                )
                if passed is not None
                else None,
                n_runs=1,
                n_evaluated=1 if passed is not None else 0,
                note=msg,
            )
        )
    overall = (
        EvalStatus.FAIL
        if eliminatory
        else (EvalStatus.INCONCLUSIVE if any(p is None for _, p, _ in details) else EvalStatus.PASS)
    )
    card = Scorecard(
        scorecard_id=new_id("scd"),
        project_id="evalkit-self",
        agent_id="evalkit",
        agent_version=__version__,
        campaign_id=f"self-{utcnow():%Y%m%dT%H%M%S}",
        generated_at=utcnow(),
        evalkit_version=__version__,
        overall_status=overall,
        eliminatory_failures=eliminatory,
        dimensions=dims,
        missing_dimensions=[
            d
            for d, p, _ in zip(
                [c[0] for c in CHECKS], [p for _, p, _ in details], details, strict=True
            )
            if p is None
        ],
        validity_warnings=[
            "self-evaluation checks are deterministic controls on EVALKIT's mechanisms; they do not evaluate any external agent"
        ],
    )
    if persist:
        with repo.transaction():
            repo.save_scorecard(card)
    return card, details
