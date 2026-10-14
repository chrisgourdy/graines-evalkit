/* eslint-disable */
// GENERATED from schemas/Budget.schema.json by scripts/gen-types.mjs — do not edit.

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
