"""Versioned price registry and cost contract. See docs/COST_CONTROL.md.

An unknown tariff yields ``Cost(status=UNKNOWN)`` — never a fabricated number.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from evalkit.contracts.base import ContractModel
from evalkit.contracts.enums import CostStatus


class PriceEntry(ContractModel):
    price_id: str
    provider: str
    model_id: str
    valid_from: date
    valid_to: date | None = Field(default=None, description="None = currently valid.")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    input_per_million: Decimal | None = None
    output_per_million: Decimal | None = None
    cached_input_per_million: Decimal | None = None
    cache_creation_per_million: Decimal | None = None
    reasoning_per_million: Decimal | None = Field(
        default=None, description="None = reasoning billed as output (provider default)."
    )
    other_per_unit: dict[str, Decimal] = Field(
        default_factory=dict, description="Per-native-unit prices, e.g. {'images': 0.004}."
    )
    source: str = Field(description="URL or document the tariff was taken from.")
    verified_at: datetime
    rules: str | None = Field(default=None, description="Special billing rules, free text.")


class FxRate(ContractModel):
    base: str
    quote: str
    rate: Decimal
    source: str
    as_of: date


class Cost(ContractModel):
    status: CostStatus
    amount: Decimal | None = None
    currency: str | None = None
    price_id: str | None = Field(default=None, description="PriceEntry used, for traceability.")
    fx: FxRate | None = None
    breakdown: dict[str, Decimal] = Field(
        default_factory=dict, description="Per-category amounts (input, output, cache, ...)."
    )
    note: str | None = None

    @classmethod
    def unknown(cls, note: str) -> Cost:
        return cls(status=CostStatus.UNKNOWN, note=note)
