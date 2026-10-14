"""Event factory: the only place that stamps version, timestamp and ids on audit events."""

from __future__ import annotations

from typing import Any

from evalkit import __version__
from evalkit.contracts import AuditEvent, EventType, Severity, new_id, utcnow

_SECRET_KEYS = ("api_key", "authorization", "token", "secret", "password")


def redact(payload: dict[str, Any]) -> dict[str, Any]:
    """Shallow+nested redaction of obvious secret keys. Central, conservative."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if any(s in key.lower() for s in _SECRET_KEYS):
            out[key] = "<redacted>"
        elif isinstance(value, dict):
            out[key] = redact(value)
        else:
            out[key] = value
    return out


def make_event(
    event_type: EventType,
    *,
    component: str,
    actor: str = "system",
    severity: Severity = Severity.INFO,
    payload: dict[str, Any] | None = None,
    **ids: Any,
) -> AuditEvent:
    return AuditEvent(
        event_id=new_id("evt"),
        timestamp=utcnow(),
        event_type=event_type,
        severity=severity,
        actor=actor,
        component=component,
        version=__version__,
        payload=redact(payload or {}),
        **ids,
    )
