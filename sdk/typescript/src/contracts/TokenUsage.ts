/* eslint-disable */
// GENERATED from schemas/TokenUsage.schema.json by scripts/gen-types.mjs — do not edit.

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
export type SchemaVersion = string;
/**
 * Origin of a token-usage figure (see docs/TOKEN_ACCOUNTING.md).
 */
export type UsageSource = "REPORTED" | "ESTIMATED" | "UNKNOWN";
export type TotalTokens = number | null;

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
  schema_version?: SchemaVersion;
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
