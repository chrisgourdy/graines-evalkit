/* eslint-disable */
// GENERATED from schemas/AuditEvent.schema.json by scripts/gen-types.mjs — do not edit.

/**
 * 'system', 'scheduler', 'cli:<user>', 'api:<key_id>', 'agent:<id>'.
 */
export type Actor = string;
export type AgentId = string | null;
export type AgentVersion = string | null;
export type CampaignId = string | null;
/**
 * Emitting module, e.g. 'core', 'cost_controller'.
 */
export type Component = string;
/**
 * event_id this event corrects.
 */
export type Corrects = string | null;
export type CorrelationId = string | null;
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
export type DurationMs = number | null;
export type EventId = string;
export type EventType =
  | "project.created"
  | "config.changed"
  | "campaign.started"
  | "campaign.ended"
  | "scenario.started"
  | "scenario.ended"
  | "agent.called"
  | "model.called"
  | "tool.called"
  | "usage.recorded"
  | "error"
  | "retry"
  | "budget.reserved"
  | "budget.settled"
  | "budget.released"
  | "budget.threshold"
  | "budget.blocked"
  | "evaluation.result"
  | "baseline.changed"
  | "regression.detected"
  | "incident.opened"
  | "fix.proposed"
  | "test.result"
  | "validation.decision"
  | "version.changed"
  | "migration"
  | "permission.changed"
  | "human.intervention"
  | "correction";
export type ParentSpanId = string | null;
/**
 * Artifact reference, never inline secrets.
 */
export type PayloadRef = string | null;
export type ProjectId = string | null;
export type RunId = string | null;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion2 = string;
/**
 * Monotonic per-store sequence assigned by the store.
 */
export type Sequence = number | null;
export type Severity = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type SpanId = string | null;
export type Status = string | null;
export type Timestamp = string;
export type TraceId = string | null;
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
export type SchemaVersion3 = string;
/**
 * Origin of a token-usage figure (see docs/TOKEN_ACCOUNTING.md).
 */
export type UsageSource = "REPORTED" | "ESTIMATED" | "UNKNOWN";
export type TotalTokens = number | null;
/**
 * EVALKIT version that emitted the event.
 */
export type Version = string;

export interface AuditEvent {
  actor: Actor;
  agent_id?: AgentId;
  agent_version?: AgentVersion;
  campaign_id?: CampaignId;
  component: Component;
  corrects?: Corrects;
  correlation_id?: CorrelationId;
  cost?: Cost | null;
  duration_ms?: DurationMs;
  event_id: EventId;
  event_type: EventType;
  parent_span_id?: ParentSpanId;
  payload?: Payload;
  payload_ref?: PayloadRef;
  project_id?: ProjectId;
  run_id?: RunId;
  schema_version?: SchemaVersion2;
  sequence?: Sequence;
  severity?: Severity;
  span_id?: SpanId;
  status?: Status;
  timestamp: Timestamp;
  trace_id?: TraceId;
  usage?: TokenUsage | null;
  version: Version;
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
/**
 * Small, redacted, structured payload.
 */
export interface Payload {
  [k: string]: unknown;
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
  schema_version?: SchemaVersion3;
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
