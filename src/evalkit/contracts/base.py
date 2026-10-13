"""Base model and helpers for all contracts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_SCHEMA_VERSION = "1.0.0"
"""Semantic version of the contract set. Bump MAJOR on breaking change (requires migration)."""


def utcnow() -> datetime:
    """Timezone-aware UTC now. All timestamps in EVALKIT are UTC."""
    return datetime.now(tz=UTC)


def new_id(prefix: str) -> str:
    """Stable, sortable-enough opaque identifier: ``<prefix>_<uuid4 hex>``."""
    return f"{prefix}_{uuid.uuid4().hex}"


class ContractModel(BaseModel):
    """Common base: strict, frozen-by-default serialization-friendly model."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        ser_json_timedelta="float",
        use_enum_values=False,
    )

    schema_version: str = Field(
        default=CONTRACT_SCHEMA_VERSION,
        description="Contract schema version this object was produced with.",
    )
