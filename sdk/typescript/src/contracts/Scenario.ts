/* eslint-disable */
// GENERATED from schemas/Scenario.schema.json by scripts/gen-types.mjs — do not edit.

export type AgentId = string;
export type Currency = string;
export type MaxCost = number | null;
export type MaxLatencyMs = number | null;
export type MaxTokens = number | null;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion = string;
/**
 * Mandatory constraints.
 */
export type Constraints = string[];
export type Criticality = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
/**
 * DEVELOPMENT data may be used to fix an agent; HOLDOUT is protected and only evaluates.
 */
export type DatasetKind = "DEVELOPMENT" | "HOLDOUT";
export type Description = string;
export type ExpectedBehavior = string;
export type Name = string;
export type Objective = string;
export type ProjectId = string;
export type Author = string;
export type CreatedAt = string;
/**
 * Where the scenario comes from (handwritten, incident replay, ...).
 */
export type Origin = string;
/**
 * VCS revision or document version.
 */
export type Revision = string | null;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion1 = string;
export type Repetitions = number;
export type ScenarioId = string;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion2 = string;
export type SourcesOfTruth = string[];
export type Description1 = string | null;
export type MinPassRate = number | null;
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
export type RequiredDimensions = Dimension[];
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion3 = string;
export type Tags = string[];
/**
 * @minItems 1
 */
export type Verifications = [VerificationSpec, ...VerificationSpec[]];
/**
 * If True, a FAIL is eliminatory regardless of other scores.
 */
export type Blocking = boolean;
/**
 * Registered evaluator id, e.g. 'exact_match', 'json_schema'.
 */
export type Evaluator = string;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion4 = string;
/**
 * Optional scoring weight.
 */
export type Weight = number | null;
/**
 * Scenario version (semver). Changing expectations bumps it.
 */
export type Version = string;

export interface Scenario {
  agent_id: AgentId;
  budget?: BudgetLimit;
  constraints?: Constraints;
  context?: Context;
  criticality?: Criticality;
  dataset?: DatasetKind;
  description: Description;
  expected_behavior: ExpectedBehavior;
  inputs: Inputs;
  name: Name;
  objective: Objective;
  project_id: ProjectId;
  provenance: Provenance;
  reference_outputs?: ReferenceOutputs;
  repetitions?: Repetitions;
  scenario_id: ScenarioId;
  schema_version?: SchemaVersion2;
  sources_of_truth?: SourcesOfTruth;
  success?: SuccessCriteria;
  tags?: Tags;
  verifications: Verifications;
  version: Version;
}
export interface BudgetLimit {
  currency?: Currency;
  max_cost?: MaxCost;
  max_latency_ms?: MaxLatencyMs;
  max_tokens?: MaxTokens;
  schema_version?: SchemaVersion;
}
/**
 * Context and fixtures.
 */
export interface Context {
  [k: string]: unknown;
}
/**
 * Inputs handed to the adapter.
 */
export interface Inputs {
  [k: string]: unknown;
}
export interface Provenance {
  author: Author;
  created_at: CreatedAt;
  origin: Origin;
  revision?: Revision;
  schema_version?: SchemaVersion1;
}
/**
 * Ground-truth references used by evaluators.
 */
export interface ReferenceOutputs {
  [k: string]: unknown;
}
export interface SuccessCriteria {
  description?: Description1;
  min_pass_rate?: MinPassRate;
  required_dimensions?: RequiredDimensions;
  schema_version?: SchemaVersion3;
}
/**
 * One verification method applied to the run. Resolved by the evaluator registry.
 */
export interface VerificationSpec {
  blocking?: Blocking;
  dimension: Dimension;
  evaluator: Evaluator;
  params?: Params;
  schema_version?: SchemaVersion4;
  weight?: Weight;
}
export interface Params {
  [k: string]: unknown;
}
