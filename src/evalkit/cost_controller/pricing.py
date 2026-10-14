"""Cost computation from a usage record and a versioned PriceEntry.

Rules:
* unknown price → Cost(UNKNOWN); UNKNOWN usage → Cost(UNKNOWN); ESTIMATED usage → Cost(ESTIMATED);
* declared subsets are removed from their parent before pricing the parent, and priced at
  their own tariff when one exists, else at the parent's tariff (never twice);
* native units (images, …) are priced per unit when ``other_per_unit`` has the key, else
  the cost is marked ESTIMATED with a note (known part only).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import yaml

from evalkit.contracts import Cost, CostStatus, PriceEntry, TokenUsage, UsageSource
from evalkit.storage.sqlite import SQLiteRepository

_MILLION = Decimal(1_000_000)
_Q = Decimal("0.000001")


def _per_million(tokens: int, price: Decimal | None) -> Decimal | None:
    if price is None:
        return None
    return (Decimal(tokens) * price / _MILLION).quantize(_Q, rounding=ROUND_HALF_UP)


def compute_cost(usage: TokenUsage, price: PriceEntry | None) -> Cost:
    if price is None:
        return Cost.unknown("no price entry for provider/model at campaign date")
    if usage.source is UsageSource.UNKNOWN:
        return Cost.unknown("usage UNKNOWN")
    inp = usage.input_tokens or 0
    out = usage.output_tokens or 0
    cached = usage.cached_input_tokens or 0
    created = usage.cache_creation_tokens or 0
    reasoning = usage.reasoning_tokens or 0
    # remove declared subsets from their parents
    if usage.subsets.get("cached_input_tokens") == "input_tokens":
        inp -= cached
    if usage.subsets.get("cache_creation_tokens") == "input_tokens":
        inp -= created
    if usage.subsets.get("reasoning_tokens") == "output_tokens":
        out -= reasoning
    inp, out = max(inp, 0), max(out, 0)
    breakdown: dict[str, Decimal] = {}
    notes: list[str] = []

    def add(key: str, tokens: int, tariff: Decimal | None, fallback: Decimal | None) -> None:
        if tokens == 0:
            return
        value = _per_million(tokens, tariff if tariff is not None else fallback)
        if value is None:
            notes.append(f"no tariff for {key}")
            return
        breakdown[key] = value

    add("input", inp, price.input_per_million, None)
    add("output", out, price.output_per_million, None)
    add("cached_input", cached, price.cached_input_per_million, price.input_per_million)
    add("cache_creation", created, price.cache_creation_per_million, price.input_per_million)
    add("reasoning", reasoning, price.reasoning_per_million, price.output_per_million)
    for unit, qty in usage.native_units.items():
        tariff = price.other_per_unit.get(unit)
        if tariff is None:
            notes.append(f"no tariff for native unit {unit!r}")
            continue
        breakdown[f"unit:{unit}"] = (Decimal(str(qty)) * tariff).quantize(
            _Q, rounding=ROUND_HALF_UP
        )
    amount = sum(breakdown.values(), Decimal(0))
    if usage.source is UsageSource.ESTIMATED or notes:
        status = CostStatus.ESTIMATED
    else:
        status = CostStatus.MEASURED
    if not breakdown and notes:
        return Cost.unknown("; ".join(notes))
    return Cost(
        status=status,
        amount=amount,
        currency=price.currency,
        price_id=price.price_id,
        breakdown=breakdown,
        note="; ".join(notes) or None,
    )


def import_prices(repo: SQLiteRepository, path: Path) -> list[PriceEntry]:
    """Load a YAML list of PriceEntry objects into the registry (INSERT OR REPLACE by id)."""
    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    entries = [PriceEntry.model_validate(item) for item in (raw or [])]
    with repo.transaction():
        for entry in entries:
            repo.save_price(entry)
    return entries


def find_price_for(repo: SQLiteRepository, usage: TokenUsage, on: date) -> PriceEntry | None:
    return repo.find_price(usage.provider, usage.model, on.isoformat())
