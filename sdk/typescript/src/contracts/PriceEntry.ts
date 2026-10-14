/* eslint-disable */
// GENERATED from schemas/PriceEntry.schema.json by scripts/gen-types.mjs — do not edit.

export type CacheCreationPerMillion = number | string | null;
export type CachedInputPerMillion = number | string | null;
export type Currency = string;
export type InputPerMillion = number | string | null;
export type ModelId = string;
export type OutputPerMillion = number | string | null;
export type PriceId = string;
export type Provider = string;
/**
 * None = reasoning billed as output (provider default).
 */
export type ReasoningPerMillion = number | string | null;
/**
 * Special billing rules, free text.
 */
export type Rules = string | null;
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion = string;
/**
 * URL or document the tariff was taken from.
 */
export type Source = string;
export type ValidFrom = string;
/**
 * None = currently valid.
 */
export type ValidTo = string | null;
export type VerifiedAt = string;

export interface PriceEntry {
  cache_creation_per_million?: CacheCreationPerMillion;
  cached_input_per_million?: CachedInputPerMillion;
  currency?: Currency;
  input_per_million?: InputPerMillion;
  model_id: ModelId;
  other_per_unit?: OtherPerUnit;
  output_per_million?: OutputPerMillion;
  price_id: PriceId;
  provider: Provider;
  reasoning_per_million?: ReasoningPerMillion;
  rules?: Rules;
  schema_version?: SchemaVersion;
  source: Source;
  valid_from: ValidFrom;
  valid_to?: ValidTo;
  verified_at: VerifiedAt;
}
/**
 * Per-native-unit prices, e.g. {'images': 0.004}.
 */
export interface OtherPerUnit {
  [k: string]: number | string;
}
