"""Token usage contract (TOKEN_METER). See docs/TOKEN_ACCOUNTING.md.

Rules encoded here:
* sub-categories (cached_input, cache_creation, reasoning) may already be included in
  ``input``/``output``/``total`` depending on the provider — they are never blindly summed;
* ``total`` is what the provider reports when REPORTED; when ESTIMATED it is the estimator's
  figure; when UNKNOWN it is ``None``;
* non-text modalities keep the provider's native units in ``native_units``.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from evalkit.contracts.base import ContractModel
from evalkit.contracts.enums import UsageSource


class TokenUsage(ContractModel):
    provider: str = Field(description="Provider identifier, e.g. 'anthropic', 'openai', 'sim'.")
    model: str = Field(description="Model identifier as billed by the provider.")
    source: UsageSource
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = Field(
        default=None, description="Cache-read input tokens. May be a subset of input_tokens."
    )
    cache_creation_tokens: int | None = Field(
        default=None, description="Cache-write tokens. May be a subset of input_tokens."
    )
    reasoning_tokens: int | None = Field(
        default=None, description="Reasoning/thinking tokens. May be a subset of output_tokens."
    )
    modality_tokens: dict[str, int] = Field(
        default_factory=dict,
        description="Tokens attributed to special modalities (e.g. 'image', 'audio').",
    )
    total_tokens: int | None = None
    native_units: dict[str, float] = Field(
        default_factory=dict,
        description="Provider-native billing units for non-token items (e.g. 'images': 2).",
    )
    subsets: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Declares inclusion relations, e.g. {'cached_input_tokens': 'input_tokens'} means "
            "cached_input is already counted inside input. Drives double-count-safe aggregation."
        ),
    )
    estimation_method: str | None = Field(
        default=None, description="Required when source=ESTIMATED (e.g. 'tiktoken:cl100k_base')."
    )
    estimation_granularity: str | None = Field(
        default=None, description="Granularity of the estimate, e.g. 'call', 'step', 'run'."
    )
    raw: dict[str, object] = Field(
        default_factory=dict, description="Provider raw usage payload for audit (secrets redacted)."
    )

    @model_validator(mode="after")
    def _check_consistency(self) -> TokenUsage:
        if self.source is UsageSource.ESTIMATED and not self.estimation_method:
            msg = "estimation_method is required when source=ESTIMATED"
            raise ValueError(msg)
        if self.source is UsageSource.UNKNOWN and any(
            v is not None for v in (self.input_tokens, self.output_tokens, self.total_tokens)
        ):
            msg = "UNKNOWN usage must not carry token figures"
            raise ValueError(msg)
        for name in (
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "cache_creation_tokens",
            "reasoning_tokens",
            "total_tokens",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                msg = f"{name} must be >= 0"
                raise ValueError(msg)
        return self

    def billable_total(self) -> int | None:
        """Total tokens without double counting declared subsets.

        Returns ``None`` when the figure cannot be established.
        """
        if self.source is UsageSource.UNKNOWN:
            return None
        if self.total_tokens is not None:
            return self.total_tokens
        if self.input_tokens is None or self.output_tokens is None:
            return None
        total = self.input_tokens + self.output_tokens
        for field, parent in (
            ("cached_input_tokens", "input_tokens"),
            ("cache_creation_tokens", "input_tokens"),
            ("reasoning_tokens", "output_tokens"),
        ):
            value = getattr(self, field)
            if value is None:
                continue
            if self.subsets.get(field) != parent:
                total += value
        return total
