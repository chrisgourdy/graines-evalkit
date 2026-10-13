"""Audit trail port."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from evalkit.contracts import AuditEvent


class AuditTrail(Protocol):
    def emit(self, event: AuditEvent) -> AuditEvent:
        """Persist (append-only) and return the event with its store-assigned sequence."""
        ...

    def correct(self, event_id: str, reason: str, payload: dict[str, object]) -> AuditEvent:
        """Emit a correction event; never mutate the original."""
        ...

    def query(self, **filters: str) -> Iterator[AuditEvent]: ...

    def export_jsonl(self, path: str, **filters: str) -> int:
        """Write matching events as JSONL; return count."""
        ...
