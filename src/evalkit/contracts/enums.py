"""Closed vocabularies. Changing a value is a breaking contract change."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class EvalStatus(StrEnum):
    """Conclusion of an evaluation. Distinct from :class:`ControlState` (did the check run?)."""

    PASS = "PASS"  # noqa: S105
    WARNING = "WARNING"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_EVALUATED = "NOT_EVALUATED"


class ControlState(StrEnum):
    """Technical state of a check. A COMPLETED control may still conclude FAIL."""

    COMPLETED = "COMPLETED"
    ERRORED = "ERRORED"
    SKIPPED = "SKIPPED"
    TIMEOUT = "TIMEOUT"


class MeasurementKind(StrEnum):
    """Nature of a measured value. Never collapse UNAVAILABLE into 0 or PASS."""

    OBJECTIVE = "OBJECTIVE"
    STATISTICAL = "STATISTICAL"
    LLM_JUDGED = "LLM_JUDGED"
    HUMAN = "HUMAN"
    UNAVAILABLE = "UNAVAILABLE"


class UsageSource(StrEnum):
    """Origin of a token-usage figure (see docs/TOKEN_ACCOUNTING.md)."""

    REPORTED = "REPORTED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class CostStatus(StrEnum):
    MEASURED = "MEASURED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class Criticality(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Severity(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatasetKind(StrEnum):
    """DEVELOPMENT data may be used to fix an agent; HOLDOUT is protected and only evaluates."""

    DEVELOPMENT = "DEVELOPMENT"
    HOLDOUT = "HOLDOUT"


class Dimension(StrEnum):
    """Evaluated dimensions (docs/METRICS.md defines each, its method and its limits)."""

    ACCURACY = "accuracy"
    COMPLIANCE = "compliance"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    FORMAT = "format"
    CONSTRAINTS = "constraints"
    DECISION_RELIABILITY = "decision_reliability"
    TOOL_USE = "tool_use"
    STABILITY = "stability"
    ROBUSTNESS = "robustness"
    SECURITY = "security"
    LATENCY = "latency"
    TOKENS = "tokens"
    COST = "cost"
    BUSINESS = "business"


class AutonomyLevel(IntEnum):
    """docs/AUTONOMY_POLICY.md — what EVALKIT may do without a human."""

    AUTOMATIC = 1
    ISOLATED_AUTOMATIC = 2
    CONTROLLED_APPLY = 3
    HUMAN_VALIDATION = 4
