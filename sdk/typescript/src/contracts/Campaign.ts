/* eslint-disable */
// GENERATED from schemas/Campaign.schema.json by scripts/gen-types.mjs — do not edit.

export type AgentId = string;
export type AgentVersion = string;
export type BaselineCampaignId = string | null;
export type BudgetId = string;
export type Currency = string;
/**
 * Parent budget_id.
 */
export type InheritsFrom = string | null;
export type MaxCost = number | null;
export type MaxTokens = number | null;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion = string;
export type BudgetScope = "organization" | "project" | "agent" | "campaign" | "day" | "month" | "evaluation_type";
/**
 * Id of the scoped entity (project_id, campaign_id, ...).
 */
export type ScopeRef = string;
export type Info = number;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion1 = string;
export type Warning = number;
export type CampaignId = string;
export type CreatedAt = string;
export type DryRun = boolean;
export type EndedAt = string | null;
export type EvalkitVersion = string;
/**
 * 'historical' | 'conservative_default' | 'mixed'.
 */
export type Basis = string;
export type Currency1 = string;
export type ExpectedAgentCost = number | null;
export type ExpectedEvaluatorCost = number | null;
export type ExpectedExternalCost = number | null;
export type ExpectedRetryCost = number | null;
export type ExpectedTokens = number | null;
export type PlannedRuns = number;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion2 = string;
/**
 * How the forecast was built and how uncertain it is.
 */
export type Uncertainty = string;
/**
 * PriceEntry ids frozen for this campaign.
 */
export type PriceSnapshotIds = string[];
export type Profile = "QUICK" | "STANDARD" | "DEEP" | "EXTENDED";
export type ProjectId = string;
export type RepetitionsOverride = number | null;
/**
 * @minItems 1
 */
export type ScenarioIds = [string, ...string[]];
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion3 = string;
export type Seed = number | null;
export type StartedAt = string | null;
export type CampaignStatus =
  "PLANNED" | "DRY_RUN" | "RUNNING" | "SUSPENDED" | "COMPLETED" | "STOPPED_BUDGET" | "STOPPED_ELIMINATORY" | "FAILED";
export type StopReason = string | null;

export interface Campaign {
  agent_id: AgentId;
  agent_version: AgentVersion;
  baseline_campaign_id?: BaselineCampaignId;
  budget?: Budget | null;
  campaign_id: CampaignId;
  created_at: CreatedAt;
  dry_run?: DryRun;
  ended_at?: EndedAt;
  evalkit_version: EvalkitVersion;
  plan?: CampaignPlan | null;
  price_snapshot_ids?: PriceSnapshotIds;
  profile: Profile;
  project_id: ProjectId;
  repetitions_override?: RepetitionsOverride;
  scenario_ids: ScenarioIds;
  schema_version?: SchemaVersion3;
  seed?: Seed;
  started_at?: StartedAt;
  status?: CampaignStatus;
  stop_reason?: StopReason;
}
export interface Budget {
  budget_id: BudgetId;
  currency?: Currency;
  inherits_from?: InheritsFrom;
  max_cost?: MaxCost;
  max_tokens?: MaxTokens;
  schema_version?: SchemaVersion;
  scope: BudgetScope;
  scope_ref: ScopeRef;
  thresholds?: BudgetThresholds;
}
/**
 * Fractions of the cap (0-1). info < warning < 1.0 (blocking).
 */
export interface BudgetThresholds {
  info?: Info;
  schema_version?: SchemaVersion1;
  warning?: Warning;
}
/**
 * Pre-execution forecast (COST_CONTROLLER). Uncertainty is explicit, never hidden.
 */
export interface CampaignPlan {
  basis: Basis;
  currency?: Currency1;
  expected_agent_cost?: ExpectedAgentCost;
  expected_evaluator_cost?: ExpectedEvaluatorCost;
  expected_external_cost?: ExpectedExternalCost;
  expected_retry_cost?: ExpectedRetryCost;
  expected_tokens?: ExpectedTokens;
  planned_runs: PlannedRuns;
  schema_version?: SchemaVersion2;
  uncertainty: Uncertainty;
}
