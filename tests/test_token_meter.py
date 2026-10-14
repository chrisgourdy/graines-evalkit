"""TOKEN_METER: provider conventions, attribution, double-count-safe aggregation."""

from __future__ import annotations

from decimal import Decimal

from evalkit.contracts import Cost, CostStatus, TokenUsage, UsageSource
from evalkit.storage import SQLiteRepository
from evalkit.token_meter import (
    SQLiteTokenMeter,
    UsageAttribution,
    estimate_by_chars,
    from_anthropic,
    from_openai,
    normalize,
)

# Fixture payloads follow the providers' documented response shapes (not live captures).
ANTHROPIC_USAGE = {
    "input_tokens": 100,
    "output_tokens": 40,
    "cache_read_input_tokens": 300,
    "cache_creation_input_tokens": 50,
}
OPENAI_CHAT_USAGE = {
    "prompt_tokens": 400,
    "completion_tokens": 120,
    "total_tokens": 520,
    "prompt_tokens_details": {"cached_tokens": 300},
    "completion_tokens_details": {"reasoning_tokens": 80},
}
OPENAI_RESPONSES_USAGE = {
    "input_tokens": 400,
    "output_tokens": 120,
    "total_tokens": 520,
    "input_tokens_details": {"cached_tokens": 300},
    "output_tokens_details": {"reasoning_tokens": 80},
}


def test_anthropic_cache_tokens_are_not_subsets() -> None:
    u = from_anthropic("claude-x", ANTHROPIC_USAGE)
    assert u.source is UsageSource.REPORTED
    assert u.subsets == {}
    # input excludes cache reads/writes → total adds all four categories once
    assert u.total_tokens == 490 and u.billable_total() == 490


def test_openai_cached_and_reasoning_are_subsets() -> None:
    for payload in (OPENAI_CHAT_USAGE, OPENAI_RESPONSES_USAGE):
        u = from_openai("gpt-x", payload)
        assert u.subsets == {
            "cached_input_tokens": "input_tokens",
            "reasoning_tokens": "output_tokens",
        }
        assert u.billable_total() == 520  # provider total wins; subsets never added again
        without_total = u.model_copy(update={"total_tokens": None})
        assert without_total.billable_total() == 520


def test_unknown_provider_and_missing_fields_yield_unknown() -> None:
    assert normalize("mystery", "m", {"x": 1}).source is UsageSource.UNKNOWN
    assert from_anthropic("m", {"output_tokens": 3}).source is UsageSource.UNKNOWN
    assert from_openai("m", {}).source is UsageSource.UNKNOWN


def test_estimator_is_flagged() -> None:
    u = estimate_by_chars("local", "llama", "a" * 40, "b" * 8)
    assert u.source is UsageSource.ESTIMATED and u.estimation_method == "chars/4"
    assert (u.input_tokens, u.output_tokens) == (10, 2)


def _usage(src: UsageSource, inp: int = 10, out: int = 5, **kw: object) -> TokenUsage:
    if src is UsageSource.UNKNOWN:
        return TokenUsage(provider="p", model="m", source=src)
    return TokenUsage(  # type: ignore[arg-type]
        provider="p",
        model="m",
        source=src,
        input_tokens=inp,
        output_tokens=out,
        estimation_method="chars/4" if src is UsageSource.ESTIMATED else None,
        **kw,
    )


def test_meter_aggregate_statuses_and_no_unknown_summing(repo: SQLiteRepository) -> None:
    meter = SQLiteTokenMeter(repo)
    attr = UsageAttribution(project_id="p", agent_id="a", campaign_id="c1", run_id="r1")
    meter.record(
        _usage(UsageSource.REPORTED),
        attr,
        Cost(status=CostStatus.MEASURED, amount=Decimal("0.5"), currency="USD"),
    )
    agg = meter.aggregate(campaign_id="c1")
    assert agg["status"] == "REPORTED" and agg["tokens"]["billable_total"] == 15
    assert agg["cost"]["status"] == "MEASURED" and agg["cost"]["known_amount"] == 0.5

    meter.record(
        _usage(UsageSource.ESTIMATED, 20, 10),
        attr,
        Cost(status=CostStatus.ESTIMATED, amount=Decimal("1"), currency="USD"),
    )
    agg = meter.aggregate(campaign_id="c1")
    assert agg["status"] == "ESTIMATED" and agg["tokens"]["billable_total"] == 45
    assert agg["cost"]["status"] == "ESTIMATED"

    meter.record(_usage(UsageSource.UNKNOWN), attr, Cost.unknown("no price"))
    agg = meter.aggregate(campaign_id="c1")
    assert agg["status"] == "PARTIAL"
    assert agg["records"]["unknown"] == 1
    assert agg["tokens"]["billable_total"] == 45  # unknown not summed as 0
    assert agg["cost"]["status"] == "PARTIAL" and agg["cost"]["records_unknown"] == 1

    assert meter.aggregate(campaign_id="nope")["status"] == "NO_DATA"


def test_meter_attribution_filters_and_history(repo: SQLiteRepository) -> None:
    meter = SQLiteTokenMeter(repo)
    for run in ("r1", "r2"):
        meter.record(
            _usage(UsageSource.REPORTED, 100, 50),
            UsageAttribution(
                project_id="p",
                agent_id="a",
                agent_version="1",
                campaign_id="c",
                run_id=run,
                period="2026-10-01",
            ),
        )
    meter.record(
        _usage(UsageSource.REPORTED, 7, 3),
        UsageAttribution(
            project_id="p", agent_id="a", campaign_id="c", run_id="r1", evaluator_id="judge"
        ),
    )
    assert meter.aggregate(run_id="r1")["tokens"]["billable_total"] == 160
    assert meter.aggregate(evaluator_id="judge")["tokens"]["billable_total"] == 10
    assert meter.aggregate(project_id="p", period="2026-10-01")["records"]["total"] == 2
    assert sorted(meter.per_run_history("p", "a")) == [150, 150]  # evaluator usage excluded
