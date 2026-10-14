/* eslint-disable */
// GENERATED from schemas/Run.schema.json by scripts/gen-types.mjs — do not edit.

export type AgentId = string;
export type AgentVersion = string;
/**
 * Repetition index within the campaign (1-based).
 */
export type Attempt = number;
export type CampaignId = string;
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
export type EndedAt = string | null;
export type Error = string | null;
export type LatencyMs = number | null;
/**
 * Artifact reference of the output.
 */
export type OutputRef = string | null;
export type ProjectId = string;
export type RunId = string;
export type ScenarioId = string;
export type ScenarioVersion = string;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion2 = string;
/**
 * Seed handed to stochastic adapters.
 */
export type Seed = number | null;
export type StartedAt = string | null;
export type RunStatus = "PENDING" | "RUNNING" | "COMPLETED" | "ERRORED" | "TIMEOUT" | "BUDGET_BLOCKED" | "CANCELLED";
export type TraceId = string | null;
export type Completed = boolean;
export type RunId1 = string;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion3 = string;
/**
 * Action label (tool name, decision label, 'generate', ...).
 */
export type Action = string;
export type DurationMs = number | null;
export type EndedAt1 = string | null;
export type Error1 = string | null;
export type Index = number;
export type StepKind = "llm_call" | "tool_call" | "decision" | "retry" | "error" | "human" | "terminal";
/**
 * Observable state after the action.
 */
export type NextState = string | null;
/**
 * Reference to the stored artifact (inputs/outputs), if retained.
 */
export type PayloadRef = string | null;
/**
 * Index of the step being retried.
 */
export type RetryOf = number | null;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion4 = string;
export type StartedAt1 = string;
/**
 * Observable state label before the action (adapter-defined).
 */
export type State = string;
export type ToolName = string | null;
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
export type SchemaVersion5 = string;
/**
 * Origin of a token-usage figure (see docs/TOKEN_ACCOUNTING.md).
 */
export type UsageSource = "REPORTED" | "ESTIMATED" | "UNKNOWN";
export type TotalTokens = number | null;
export type Steps = TrajectoryStep[];
export type TerminalState = string | null;
export type Usage = TokenUsage[];

export interface Run {
  agent_id: AgentId;
  agent_version: AgentVersion;
  attempt: Attempt;
  campaign_id: CampaignId;
  cost?: Cost | null;
  ended_at?: EndedAt;
  error?: Error;
  latency_ms?: LatencyMs;
  output?: unknown;
  output_ref?: OutputRef;
  project_id: ProjectId;
  run_id: RunId;
  scenario_id: ScenarioId;
  scenario_version: ScenarioVersion;
  schema_version?: SchemaVersion2;
  seed?: Seed;
  started_at?: StartedAt;
  status?: RunStatus;
  trace_id?: TraceId;
  trajectory?: Trajectory | null;
  usage?: Usage;
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
export interface Trajectory {
  completed?: Completed;
  run_id: RunId1;
  schema_version?: SchemaVersion3;
  steps?: Steps;
  terminal_state?: TerminalState;
}
export interface TrajectoryStep {
  action: Action;
  attributes?: Attributes;
  duration_ms?: DurationMs;
  ended_at?: EndedAt1;
  error?: Error1;
  index: Index;
  kind: StepKind;
  next_state?: NextState;
  payload_ref?: PayloadRef;
  retry_of?: RetryOf;
  schema_version?: SchemaVersion4;
  started_at: StartedAt1;
  state: State;
  tool_name?: ToolName;
  usage?: TokenUsage | null;
}
export interface Attributes {
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
  schema_version?: SchemaVersion5;
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
