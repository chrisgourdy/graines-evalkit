"""Provider usage conventions → canonical TokenUsage with explicit subset declarations.

The shapes below follow the providers' *documented* response formats as known at the time of
writing; they are exercised against fixture payloads, not live calls (EK-0007 tracks the
verification against real payloads). Each entry says which sub-categories are already
included in a parent figure, so ``billable_total()`` never double counts.

* anthropic (Messages API ``usage``): ``input_tokens`` EXCLUDES ``cache_read_input_tokens``
  and ``cache_creation_input_tokens`` (they are billed separately) → no subset relation.
* openai (Chat/Responses ``usage``): ``prompt_tokens`` INCLUDES
  ``prompt_tokens_details.cached_tokens``; ``completion_tokens`` INCLUDES
  ``completion_tokens_details.reasoning_tokens`` → both declared as subsets.
* sim: synthetic, ``total_tokens`` authoritative.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evalkit.contracts import TokenUsage, UsageSource


def _int(d: dict[str, Any], *path: str) -> int | None:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return int(cur) if isinstance(cur, int | float) else None


def from_anthropic(model: str, usage: dict[str, Any]) -> TokenUsage:
    inp = _int(usage, "input_tokens")
    out = _int(usage, "output_tokens")
    cached = _int(usage, "cache_read_input_tokens")
    created = _int(usage, "cache_creation_input_tokens")
    if inp is None or out is None:
        return TokenUsage(provider="anthropic", model=model, source=UsageSource.UNKNOWN, raw=usage)
    total = inp + out + (cached or 0) + (created or 0)
    return TokenUsage(
        provider="anthropic",
        model=model,
        source=UsageSource.REPORTED,
        input_tokens=inp,
        output_tokens=out,
        cached_input_tokens=cached,
        cache_creation_tokens=created,
        total_tokens=total,
        subsets={},  # cache figures are NOT inside input_tokens for Anthropic
        raw=usage,
    )


def from_openai(model: str, usage: dict[str, Any]) -> TokenUsage:
    inp = _int(usage, "prompt_tokens")
    out = _int(usage, "completion_tokens")
    if inp is None:  # Responses API naming
        inp = _int(usage, "input_tokens")
        out = _int(usage, "output_tokens")
        cached = _int(usage, "input_tokens_details", "cached_tokens")
        reasoning = _int(usage, "output_tokens_details", "reasoning_tokens")
    else:
        cached = _int(usage, "prompt_tokens_details", "cached_tokens")
        reasoning = _int(usage, "completion_tokens_details", "reasoning_tokens")
    if inp is None or out is None:
        return TokenUsage(provider="openai", model=model, source=UsageSource.UNKNOWN, raw=usage)
    total = _int(usage, "total_tokens")
    return TokenUsage(
        provider="openai",
        model=model,
        source=UsageSource.REPORTED,
        input_tokens=inp,
        output_tokens=out,
        cached_input_tokens=cached,
        reasoning_tokens=reasoning,
        total_tokens=total if total is not None else inp + out,
        subsets={"cached_input_tokens": "input_tokens", "reasoning_tokens": "output_tokens"},
        raw=usage,
    )


def estimate_by_chars(
    provider: str, model: str, prompt_text: str, completion_text: str, chars_per_token: float = 4.0
) -> TokenUsage:
    """Documented fallback estimator (ESTIMATED, method recorded). Coarse by construction."""
    inp = max(1, round(len(prompt_text) / chars_per_token))
    out = max(1, round(len(completion_text) / chars_per_token))
    return TokenUsage(
        provider=provider,
        model=model,
        source=UsageSource.ESTIMATED,
        input_tokens=inp,
        output_tokens=out,
        total_tokens=inp + out,
        estimation_method=f"chars/{chars_per_token:g}",
        estimation_granularity="call",
    )


NORMALIZERS: dict[str, Callable[[str, dict[str, Any]], TokenUsage]] = {
    "anthropic": from_anthropic,
    "openai": from_openai,
}


def normalize(provider: str, model: str, usage: dict[str, Any]) -> TokenUsage:
    """Normalise a provider payload; unknown providers yield UNKNOWN with the raw kept."""
    fn = NORMALIZERS.get(provider)
    if fn is None:
        return TokenUsage(provider=provider, model=model, source=UsageSource.UNKNOWN, raw=usage)
    return fn(model, usage)
