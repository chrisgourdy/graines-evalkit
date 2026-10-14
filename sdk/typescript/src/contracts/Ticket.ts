/* eslint-disable */
// GENERATED from schemas/Ticket.schema.json by scripts/gen-types.mjs — do not edit.

export type AgentId = string;
export type AgentVersion = string;
export type Component = string | null;
export type CreatedAt = string;
export type Decision = string | null;
export type Description = string;
/**
 * run/result/event ids.
 */
export type EvidenceRefs = string[];
export type Expected = string;
/**
 * Append-only transition log.
 */
export type History = string[];
export type EvidenceRefs1 = string[];
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion = string;
/**
 * 'open' | 'confirmed' | 'rejected'.
 */
export type Status = string;
export type Text = string;
export type Hypotheses = Hypothesis[];
export type Impact = string;
export type Observed = string;
export type PostFixResults = string[];
/**
 * 1 = highest.
 */
export type Priority = number;
export type ProjectId = string;
export type ProposedFix = string | null;
export type RelatedTests = string[];
/**
 * Similar tickets, kept distinct.
 */
export type RelatedTickets = string[];
/**
 * Contract schema version this object was produced with.
 */
export type SchemaVersion1 = string;
export type Criticality = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type TicketStatus =
  "OPEN" | "TRIAGED" | "DIAGNOSED" | "FIX_PROPOSED" | "TESTING" | "VALIDATED" | "REJECTED" | "CLOSED" | "DUPLICATE";
export type TicketId = string;
export type Title = string;
export type UpdatedAt = string;
export type WorkflowVersion = string;

export interface Ticket {
  agent_id: AgentId;
  agent_version: AgentVersion;
  component?: Component;
  created_at: CreatedAt;
  decision?: Decision;
  description: Description;
  evidence_refs?: EvidenceRefs;
  expected: Expected;
  history?: History;
  hypotheses?: Hypotheses;
  impact: Impact;
  observed: Observed;
  post_fix_results?: PostFixResults;
  priority?: Priority;
  project_id: ProjectId;
  proposed_fix?: ProposedFix;
  related_tests?: RelatedTests;
  related_tickets?: RelatedTickets;
  schema_version?: SchemaVersion1;
  severity: Criticality;
  status?: TicketStatus;
  ticket_id: TicketId;
  title: Title;
  updated_at: UpdatedAt;
  workflow_version?: WorkflowVersion;
}
export interface Hypothesis {
  evidence_refs?: EvidenceRefs1;
  schema_version?: SchemaVersion;
  status?: Status;
  text: Text;
}
