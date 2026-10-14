/* eslint-disable */
// GENERATED from schemas/EvaluationResult.schema.json by scripts/gen-types.mjs — do not edit.

export type Blocking = boolean;
/**
 * Technical state of a check. A COMPLETED control may still conclude FAIL.
 */
export type ControlState = "COMPLETED" | "ERRORED" | "SKIPPED" | "TIMEOUT";
/**
 * Evaluated dimensions (docs/METRICS.md defines each, its method and its limits).
 */
export type Dimension =
  | "accuracy"
  | "compliance"
  | "completeness"
  | "consistency"
  | "format"
  | "constraints"
  | "decision_reliability"
  | "tool_use"
  | "stability"
  | "robustness"
  | "security"
  | "latency"
  | "tokens"
  | "cost"
  | "business";
export type EvaluatedAt = string;
export type Amount = number | string | null;
export type Currency = string | null;
export type AsOf = string;
export type Base = string;
export type Quote = string;
export type Rate = number | string;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion = string;
export type Source = string;
export type Note = string | null;
/**
 * PriceEntry used, for traceability.
 */
export type PriceId = string | null;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion1 = string;
export type CostStatus = "MEASURED" | "ESTIMATED" | "UNKNOWN";
export type EvaluatorId = string;
/**
 * Cache-write tokens. May be a subset of input_tokens.
 */
export type CacheCreationTokens = number | null;
/**
 * Cache-read input tokens. May be a subset of input_tokens.
 */
export type CachedInputTokens = number | null;
/**
 * Granularity of the estimate, e.g. 'call', 'step', 'run'.
 */
export type EstimationGranularity = string | null;
/**
 * Required when source=ESTIMATED (e.g. 'tiktoken:cl100k_base').
 */
export type EstimationMethod = string | null;
export type InputTokens = number | null;
/**
 * Model identifier as billed by the provider.
 */
export type Model = string;
export type OutputTokens = number | null;
/**
 * Provider identifier, e.g. 'anthropic', 'openai', 'sim'.
 */
export type Provider = string;
/**
 * Reasoning/thinking tokens. May be a subset of output_tokens.
 */
export type ReasoningTokens = number | null;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion2 = string;
/**
 * Origin of a token-usage figure (see docs/TOKEN_ACCOUNTING.md).
 */
export type UsageSource = "REPORTED" | "ESTIMATED" | "UNKNOWN";
export type TotalTokens = number | null;
/**
 * LLM usage of the evaluator itself (kept separate).
 */
export type EvaluatorUsage = TokenUsage[];
export type EvaluatorVersion = string;
/**
 * e.g. 'diff', 'schema_error', 'reference', 'judge_rationale'.
 */
export type Kind = string;
/**
 * Artifact reference for the full evidence.
 */
export type Ref = string | null;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion3 = string;
export type Summary = string;
export type Evidence = Evidence1[];
/**
 * Nature of a measured value. Never collapse UNAVAILABLE into 0 or PASS.
 */
export type MeasurementKind = "OBJECTIVE" | "STATISTICAL" | "LLM_JUDGED" | "HUMAN" | "UNAVAILABLE";
export type Message = string;
export type ResultId = string;
export type RunId = string;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion4 = string;
/**
 * Normalised score if any.
 */
export type Score = number | null;
/**
 * Conclusion of an evaluation. Distinct from :class:`ControlState` (did the check run?).
 */
export type EvalStatus = "PASS" | "WARNING" | "FAIL" | "INCONCLUSIVE" | "NOT_EVALUATED";
export type Unit = string | null;
/**
 * Raw measured value (latency ms, ...).
 */
export type Value = number | null;

export interface EvaluationResult {
  blocking?: Blocking;
  control_state: ControlState;
  dimension: Dimension;
  evaluated_at: EvaluatedAt;
  evaluator_cost?: Cost | null;
  evaluator_id: EvaluatorId;
  evaluator_usage?: EvaluatorUsage;
  evaluator_version: EvaluatorVersion;
  evidence?: Evidence;
  measurement: MeasurementKind;
  message?: Message;
  result_id: ResultId;
  run_id: RunId;
  schema_version?: SchemaVersion4;
  score?: Score;
  status: EvalStatus;
  unit?: Unit;
  value?: Value;
}
export interface Cost {
  amount?: Amount;
  breakdown?: Breakdown;
  currency?: Currency;
  fx?: FxRate | null;
  note?: Note;
  price_id?: PriceId;
  schema_version?: SchemaVersion1;
  status: CostStatus;
}
/**
 * Per-category amounts (input, output, cache, ...).
 */
export interface Breakdown {
  [k: string]: number | string;
}
export interface FxRate {
  as_of: AsOf;
  base: Base;
  quote: Quote;
  rate: Rate;
  schema_version?: SchemaVersion;
  source: Source;
}
export interface TokenUsage {
  cache_creation_tokens?: CacheCreationTokens;
  cached_input_tokens?: CachedInputTokens;
  estimation_granularity?: EstimationGranularity;
  estimation_method?: EstimationMethod;
  input_tokens?: InputTokens;
  modality_tokens?: ModalityTokens;
  model: Model;
  native_units?: NativeUnits;
  output_tokens?: OutputTokens;
  provider: Provider;
  raw?: Raw;
  reasoning_tokens?: ReasoningTokens;
  schema_version?: SchemaVersion2;
  source: UsageSource;
  subsets?: Subsets;
  total_tokens?: TotalTokens;
}
/**
 * Tokens attributed to special modalities (e.g. 'image', 'audio').
 */
export interface ModalityTokens {
  [k: string]: number;
}
/**
 * Provider-native billing units for non-token items (e.g. 'images': 2).
 */
export interface NativeUnits {
  [k: string]: number;
}
/**
 * Provider raw usage payload for audit (secrets redacted).
 */
export interface Raw {
  [k: string]: unknown;
}
/**
 * Declares inclusion relations, e.g. {'cached_input_tokens': 'input_tokens'} means cached_input is already counted inside input. Drives double-count-safe aggregation.
 */
export interface Subsets {
  [k: string]: string;
}
export interface Evidence1 {
  kind: Kind;
  ref?: Ref;
  schema_version?: SchemaVersion3;
  summary: Summary;
}
