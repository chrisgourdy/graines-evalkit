"""JSON Schema export — single source of truth for the TypeScript SDK types."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evalkit.contracts.base import ContractModel


def _exported_models() -> dict[str, type[ContractModel]]:
    from evalkit.contracts import (
        AuditEvent,
        Budget,
        Campaign,
        EvaluationResult,
        PriceEntry,
        Run,
        Scenario,
        Scorecard,
        Ticket,
        TokenUsage,
        Trajectory,
    )

    return {
        "Scenario": Scenario,
        "Run": Run,
        "TokenUsage": TokenUsage,
        "PriceEntry": PriceEntry,
        "EvaluationResult": EvaluationResult,
        "Campaign": Campaign,
        "Budget": Budget,
        "AuditEvent": AuditEvent,
        "Scorecard": Scorecard,
        "Ticket": Ticket,
        "Trajectory": Trajectory,
    }


def export_json_schemas(out_dir: Path) -> list[Path]:
    """Write one ``<Name>.schema.json`` per public contract. Returns written paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in _exported_models().items():
        path = out_dir / f"{name}.schema.json"
        schema = model.model_json_schema()
        schema["$id"] = f"https://graines.ai/evalkit/schemas/{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written
