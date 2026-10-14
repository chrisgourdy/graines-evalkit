# Token accounting (TOKEN_METER)

Contract: `evalkit.contracts.TokenUsage`; attribution: `token_meter.UsageAttribution`.

## 1. Status of a figure

| Source | Meaning | Required fields |
|---|---|---|
| REPORTED | returned by the provider API for that call | provider, model, figures as returned, `raw` |
| ESTIMATED | computed by a documented estimator | `estimation_method`, `estimation_granularity` |
| UNKNOWN | nothing reliable | no token figures allowed |

Estimates are never presented as measurements: reports show the source next to every figure,
and aggregates containing any ESTIMATED record are labelled ESTIMATED; any UNKNOWN record makes
the aggregate UNKNOWN for that category (it is shown as "≥ known part" with the count of unknown
records). Reported data are always preferred when available.

## 2. Categories

input, output, cached input (cache read), cache creation (cache write), reasoning, modality
tokens, total; plus provider-native units for non-token billing (images, seconds of audio, tool
calls billed per call). Sub-categories are often already included in input/output/total:
`TokenUsage.subsets` declares these inclusions per provider and `billable_total()` honours them.
Known provider conventions are catalogued in `src/evalkit/token_meter/providers.py` and
tested against fixtures that follow the documented API shapes (Anthropic: cache figures are
separate from `input_tokens`; OpenAI: `cached_tokens` ⊂ `prompt_tokens`, `reasoning_tokens` ⊂
`completion_tokens`). Verification against live payloads is tracked by EK-0007.

## 3. Attribution

Each record has exactly one attribution path: organisation → project → agent → version →
campaign → scenario → run → step → call, plus model, provider, evaluator (when the usage belongs
to an evaluator) and period. Multi-agent workflows attribute each call to the sub-agent that
made it; the orchestrating run only sums its children, it never re-records them.

## 4. OpenTelemetry mapping

Where available, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`gen_ai.request.model`, `gen_ai.system` from the OTel GenAI semantic conventions are read and
written by the audit bridge (`docs/OBSERVABILITY.md`).

## 5. Operational figures

Tokens per run / scenario / agent / campaign; cost per run / scenario / valid answer /
evaluation; evaluator cost; retry cost; error cost; project total; trends; version comparison;
EVALKIT's own consumption versus the evaluated agents'. All derived from stored records.
