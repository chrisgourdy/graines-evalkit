"""COST_CONTROLLER: pricing with subsets, registry, forecast, atomic reservations, caps,
thresholds and a multi-thread concurrency proof."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from evalkit.contracts import (
    Budget,
    BudgetScope,
    Campaign,
    CampaignStatus,
    Cost,
    CostStatus,
    EventType,
    PriceEntry,
    Profile,
    RunStatus,
    TokenUsage,
    UsageSource,
    new_id,
    utcnow,
)
from evalkit.core import CampaignRefusedError, CampaignRunner
from evalkit.cost_controller import (
    BudgetDecision,
    SQLiteCostController,
    compute_cost,
    import_prices,
)
from evalkit.storage import SQLiteRepository

ROOT = Path(__file__).resolve().parents[1]

PRICE = PriceEntry(
    price_id="p/m/2026",
    provider="p",
    model_id="m",
    valid_from=date(2026, 1, 1),
    currency="USD",
    input_per_million=Decimal("1"),
    output_per_million=Decimal("2"),
    cached_input_per_million=Decimal("0.1"),
    source="test",
    verified_at=datetime(2026, 1, 1, tzinfo=UTC),
)


def test_compute_cost_rules() -> None:
    reported = TokenUsage(
        provider="p",
        model="m",
        source=UsageSource.REPORTED,
        input_tokens=1_000_000,
        output_tokens=500_000,
    )
    c = compute_cost(reported, PRICE)
    assert c.status is CostStatus.MEASURED and c.amount == Decimal("2") and c.price_id == "p/m/2026"
    assert compute_cost(reported, None).status is CostStatus.UNKNOWN
    unknown = TokenUsage(provider="p", model="m", source=UsageSource.UNKNOWN)
    assert compute_cost(unknown, PRICE).status is CostStatus.UNKNOWN
    estimated = reported.model_copy(
        update={"source": UsageSource.ESTIMATED, "estimation_method": "x"}
    )
    assert compute_cost(estimated, PRICE).status is CostStatus.ESTIMATED


def test_compute_cost_subsets_not_double_billed() -> None:
    # OpenAI style: cached inside input → 1M input of which 400k cached
    openai_like = TokenUsage(
        provider="p",
        model="m",
        source=UsageSource.REPORTED,
        input_tokens=1_000_000,
        output_tokens=0,
        cached_input_tokens=400_000,
        subsets={"cached_input_tokens": "input_tokens"},
    )
    c = compute_cost(openai_like, PRICE)
    assert c.breakdown == {"input": Decimal("0.6"), "cached_input": Decimal("0.04")}
    # Anthropic style: cached separate → full input + cached
    anthropic_like = openai_like.model_copy(update={"subsets": {}})
    c2 = compute_cost(anthropic_like, PRICE)
    assert c2.breakdown == {"input": Decimal("1"), "cached_input": Decimal("0.04")}
    # reasoning without its own tariff falls back to output price, once
    reasoning = TokenUsage(
        provider="p",
        model="m",
        source=UsageSource.REPORTED,
        input_tokens=0,
        output_tokens=1_000_000,
        reasoning_tokens=250_000,
        subsets={"reasoning_tokens": "output_tokens"},
    )
    c3 = compute_cost(reasoning, PRICE)
    assert sum(c3.breakdown.values()) == Decimal("2")
    # native unit without tariff → ESTIMATED with note (known part only)
    images = reasoning.model_copy(update={"native_units": {"images": 3}})
    c4 = compute_cost(images, PRICE)
    assert c4.status is CostStatus.ESTIMATED and "images" in (c4.note or "")


def test_price_registry_import_and_lookup(repo: SQLiteRepository) -> None:
    entries = import_prices(repo, ROOT / "prices" / "sim.prices.yaml")
    assert len(entries) == 2
    found = repo.find_price("sim", "sim-stochastic-1", "2026-10-14")
    assert found and found.price_id == "sim/sim-stochastic-1/2026-01-01"
    assert repo.find_price("sim", "sim-stochastic-1", "2025-12-31") is None
    assert repo.find_price("sim", "nope", "2026-10-14") is None


def _campaign(cid: str = "c1", project: str = "demo", agent: str = "greeter") -> Campaign:
    return Campaign(
        campaign_id=cid,
        project_id=project,
        agent_id=agent,
        agent_version="1",
        profile=Profile.STANDARD,
        scenario_ids=["x.y.z"],
        created_at=utcnow(),
        evalkit_version="t",
    )


def test_forecast_history_vs_default() -> None:
    ctl = SQLiteCostController.__new__(SQLiteCostController)  # no repo needed for forecast
    free = ctl.forecast(None, planned_runs=4, cost_bearing=False)
    assert free.expected_agent_cost == 0.0 and free.basis == "conservative_default"
    default = ctl.forecast(None, planned_runs=4, cost_bearing=True, price_per_million_hint=3.0)
    assert default.basis == "conservative_default" and default.expected_tokens == 16000
    hist = ctl.forecast(
        None,
        planned_runs=4,
        cost_bearing=True,
        history_tokens=[100, 120, 90, 500],
        price_per_million_hint=3.0,
    )
    assert hist.basis == "historical" and hist.expected_tokens == 4 * 500  # p90 per run
    assert hist.expected_retry_cost is not None and "10 %" in hist.uncertainty
    nohint = ctl.forecast(None, planned_runs=1, cost_bearing=True)
    assert nohint.expected_agent_cost is None and "cost unknown" in nohint.uncertainty


def test_reserve_settle_release_and_thresholds(repo: SQLiteRepository) -> None:
    ctl = SQLiteCostController(repo)
    ctl.save_budget(
        Budget(budget_id="b", scope=BudgetScope.PROJECT, scope_ref="demo", max_cost=1.0)
    )
    camp = _campaign()
    d1, r1 = ctl.reserve(camp, run_id="r1", expected_cost=0.6, expected_tokens=100)
    assert d1 is BudgetDecision.ALLOW and r1
    assert ctl.spent("b") == (0.6, 100)
    ctl.settle(
        r1.reservation_id,
        Cost(status=CostStatus.MEASURED, amount=Decimal("0.2"), currency="USD"),
        40,
    )
    assert ctl.spent("b") == (0.2, 40)
    d2, r2 = ctl.reserve(camp, run_id="r2", expected_cost=0.7, expected_tokens=10)
    assert d2 is BudgetDecision.ALLOW_WITH_WARNING  # 0.9 ≥ warning 0.8
    assert r2
    ctl.release(r2.reservation_id)
    assert ctl.spent("b") == (0.2, 40)
    d3, r3 = ctl.reserve(camp, run_id="r3", expected_cost=0.9, expected_tokens=None)
    assert d3 is BudgetDecision.BLOCK and r3 is None
    types = [e.event_type for e in repo.query(campaign_id="c1")]
    assert EventType.BUDGET_RESERVED in types and EventType.BUDGET_SETTLED in types
    assert EventType.BUDGET_RELEASED in types and EventType.BUDGET_BLOCKED in types
    assert EventType.BUDGET_THRESHOLD in types


def test_no_budget_blocks_and_token_cap(repo: SQLiteRepository) -> None:
    ctl = SQLiteCostController(repo)
    assert (
        ctl.reserve(_campaign(), run_id=None, expected_cost=0.0, expected_tokens=1)[0]
        is BudgetDecision.BLOCK
    )
    ctl.save_budget(
        Budget(budget_id="t", scope=BudgetScope.AGENT, scope_ref="demo/greeter", max_tokens=100)
    )
    assert (
        ctl.reserve(_campaign(), run_id=None, expected_cost=0.0, expected_tokens=60)[0]
        is BudgetDecision.ALLOW
    )
    assert (
        ctl.reserve(_campaign(), run_id=None, expected_cost=0.0, expected_tokens=60)[0]
        is BudgetDecision.BLOCK
    )


def test_unknown_observed_cost_keeps_reservation(repo: SQLiteRepository) -> None:
    ctl = SQLiteCostController(repo)
    ctl.save_budget(
        Budget(budget_id="b", scope=BudgetScope.PROJECT, scope_ref="demo", max_cost=1.0)
    )
    _, r = ctl.reserve(_campaign(), run_id="r", expected_cost=0.3, expected_tokens=None)
    assert r
    ctl.settle(r.reservation_id, Cost.unknown("no price"))
    assert ctl.spent("b")[0] == 0.3  # conservative: reserved amount kept


def test_concurrent_reservations_cannot_exceed_cap(tmp_path: Path) -> None:
    """N threads with their own connections race for a 1.0 cap in 0.3 steps: at most 3 win."""
    data = tmp_path / "data"
    setup = SQLiteRepository(data)
    setup.migrate()
    SQLiteCostController(setup).save_budget(
        Budget(budget_id="cap", scope=BudgetScope.PROJECT, scope_ref="demo", max_cost=1.0)
    )
    setup.close()
    wins: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(12)

    def worker(i: int) -> None:
        repo = SQLiteRepository(data)
        ctl = SQLiteCostController(repo)
        barrier.wait()
        decision, res = ctl.reserve(
            _campaign(cid=f"c{i}"), run_id=f"r{i}", expected_cost=0.3, expected_tokens=None
        )
        if decision is not BudgetDecision.BLOCK and res:
            with lock:
                wins.append(res.reservation_id)
        repo.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(wins) == 3, wins
    check = SQLiteRepository(data)
    assert SQLiteCostController(check).spent("cap") == (pytest.approx(0.9), 0)
    ok, _ = check.verify_chain()
    assert ok
    check.close()


def _paid_project(tmp_path: Path, demo_dir: Path, *, p_error: float = 0.0) -> Path:
    proj = tmp_path / "paid"
    (proj / "scenarios").mkdir(parents=True)
    (proj / "evalkit.yaml").write_text(
        "project_id: paid\nagents:\n  bot:\n    adapter: sim.stochastic\n    version: '1'\n"
        f"    params: {{cost_bearing: true, p_wrong: 0.0, p_error: {p_error}, p_retry: 0.0}}\n"
    )
    src = (demo_dir / "scenarios" / "greeter" / "greet-001.yaml").read_text()
    for i in range(3):
        (proj / "scenarios" / f"s{i}.yaml").write_text(
            src.replace("project_id: demo", "project_id: paid")
            .replace("agent_id: greeter", "agent_id: bot")
            .replace("scenario_id: demo.greet.001", f"scenario_id: paid.greet.{i:03d}")
        )
    return proj


def test_paid_campaign_meters_costs_and_stops_on_budget(
    repo: SQLiteRepository, tmp_path: Path, demo_dir: Path
) -> None:
    import_prices(repo, ROOT / "prices" / "sim.prices.yaml")
    proj = _paid_project(tmp_path, demo_dir)
    runner = CampaignRunner(repo)
    with pytest.raises(CampaignRefusedError, match="no applicable budget"):
        runner.plan(proj, "bot", profile=Profile.DEEP)
    # generous budget: everything runs and is metered with MEASURED cost
    runner.controller.save_budget(
        Budget(budget_id="big", scope=BudgetScope.PROJECT, scope_ref="paid", max_cost=10.0)
    )
    planned = runner.plan(proj, "bot", profile=Profile.DEEP, seed=3)
    assert planned.price and planned.campaign.price_snapshot_ids == [planned.price.price_id]
    assert planned.campaign.plan and planned.campaign.plan.basis == "conservative_default"
    camp = asyncio.run(runner.execute(planned))
    assert camp.status is CampaignStatus.COMPLETED
    runs = list(repo.list_runs(camp.campaign_id))
    assert len(runs) == 9 and all(r.cost and r.cost.status is CostStatus.MEASURED for r in runs)
    agg = runner.meter.aggregate(campaign_id=camp.campaign_id)
    assert agg["cost"]["status"] == "MEASURED" and agg["cost"]["known_amount"] > 0
    # history now exists → next forecast is historical
    planned2 = runner.plan(proj, "bot", profile=Profile.DEEP, seed=4)
    assert planned2.campaign.plan and planned2.campaign.plan.basis == "historical"
    # tiny per-campaign token budget: stops after the first run(s)
    runner.controller.save_budget(
        Budget(budget_id="tiny", scope=BudgetScope.AGENT, scope_ref="paid/bot", max_tokens=1)
    )
    planned3 = runner.plan(proj, "bot", profile=Profile.DEEP, seed=5)
    camp3 = asyncio.run(runner.execute(planned3))
    assert camp3.status is CampaignStatus.STOPPED_BUDGET
    statuses = [r.status for r in repo.list_runs(camp3.campaign_id)]
    assert RunStatus.BUDGET_BLOCKED in statuses and statuses.count(RunStatus.COMPLETED) == 0
    types = [e.event_type for e in repo.query(campaign_id=camp3.campaign_id)]
    assert EventType.BUDGET_BLOCKED in types and EventType.CAMPAIGN_ENDED in types


def test_workers_do_not_break_audit_chain(repo: SQLiteRepository, demo_dir: Path) -> None:
    runner = CampaignRunner(repo, max_workers=4)
    camp = asyncio.run(
        runner.execute(runner.plan(demo_dir, "greeter-flaky", profile=Profile.DEEP, seed=9))
    )
    assert (
        camp.status is CampaignStatus.COMPLETED and len(list(repo.list_runs(camp.campaign_id))) == 6
    )
    ok, n = repo.verify_chain()
    assert ok and n > 20
    seqs = [e.sequence for e in repo.query(campaign_id=camp.campaign_id)]
    assert seqs == sorted(seqs)
    assert new_id("x").startswith("x_")
