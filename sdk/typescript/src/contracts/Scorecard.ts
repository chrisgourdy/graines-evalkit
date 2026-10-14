/* eslint-disable */
// GENERATED from schemas/Scorecard.schema.json by scripts/gen-types.mjs — do not edit.

export type AgentId = string;
export type AgentVersion = string;
/**
 * Formula, weights, exclusions (human-readable); required with aggregate_score.
 */
export type AggregateFormula = string | null;
export type AggregateScore = number | null;
export type BaselineCampaignId = string | null;
export type CampaignId = string;
export type CostStatus = string | null;
export type Currency = string;
export type High = number;
/**
 * e.g. 0.95
 */
export type Level = number;
export type Low = number;
/**
 * e.g. 'wilson', 'bootstrap_bca', 't'.
 */
export type Method = string;
export type N = number;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion = string;
export type CriticalFailures = number;
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
export type MeanScore = number | null;
/**
 * Nature of a measured value. Never collapse UNAVAILABLE into 0 or PASS.
 */
export type MeasurementKind = "OBJECTIVE" | "STATISTICAL" | "LLM_JUDGED" | "HUMAN" | "UNAVAILABLE";
export type NEvaluated = number;
export type NRuns = number;
export type Note = string | null;
export type PassRate = number | null;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion1 = string;
/**
 * Conclusion of an evaluation. Distinct from :class:`ControlState` (did the check run?).
 */
export type EvalStatus = "PASS" | "WARNING" | "FAIL" | "INCONCLUSIVE" | "NOT_EVALUATED";
export type Dimensions = DimensionScore[];
/**
 * Scenario/evaluator ids with blocking FAIL.
 */
export type EliminatoryFailures = string[];
export type EvalkitVersion = string;
export type GeneratedAt = string;
export type MeanLatencyMs = number | null;
export type MissingDimensions = Dimension[];
export type ProjectId = string;
export type Regressions = string[];
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion2 = string;
export type ScorecardId = string;
export type TotalCost = number | null;
/**
 * Coverage, overfitting, drift, non-equivalence warnings.
 */
export type ValidityWarnings = string[];

export interface Scorecard {
  agent_id: AgentId;
  agent_version: AgentVersion;
  aggregate_formula?: AggregateFormula;
  aggregate_score?: AggregateScore;
  baseline_campaign_id?: BaselineCampaignId;
  campaign_id: CampaignId;
  cost_status?: CostStatus;
  currency?: Currency;
  dimensions: Dimensions;
  eliminatory_failures?: EliminatoryFailures;
  evalkit_version: EvalkitVersion;
  generated_at: GeneratedAt;
  mean_latency_ms?: MeanLatencyMs;
  missing_dimensions?: MissingDimensions;
  overall_status: EvalStatus;
  project_id: ProjectId;
  regressions?: Regressions;
  schema_version?: SchemaVersion2;
  scorecard_id: ScorecardId;
  total_cost?: TotalCost;
  validity_warnings?: ValidityWarnings;
}
export interface DimensionScore {
  ci?: ConfidenceInterval | null;
  critical_failures?: CriticalFailures;
  dimension: Dimension;
  mean_score?: MeanScore;
  measurement: MeasurementKind;
  n_evaluated: NEvaluated;
  n_runs: NRuns;
  note?: Note;
  pass_rate?: PassRate;
  schema_version?: SchemaVersion1;
  status: EvalStatus;
}
export interface ConfidenceInterval {
  high: High;
  level: Level;
  low: Low;
  method: Method;
  n: N;
  schema_version?: SchemaVersion;
}
