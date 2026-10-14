-- 0001 initial schema (contracts 1.0.0)
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenarios (
  scenario_id TEXT NOT NULL,
  version TEXT NOT NULL,
  project_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  dataset TEXT NOT NULL,
  json TEXT NOT NULL,
  PRIMARY KEY (scenario_id, version)
);
CREATE INDEX IF NOT EXISTS ix_scenarios_project ON scenarios(project_id, agent_id);

CREATE TABLE IF NOT EXISTS campaigns (
  campaign_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  agent_version TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_campaigns_project ON campaigns(project_id, agent_id, created_at);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  scenario_id TEXT NOT NULL,
  scenario_version TEXT NOT NULL,
  attempt INTEGER NOT NULL,
  status TEXT NOT NULL,
  json TEXT NOT NULL,
  UNIQUE (campaign_id, scenario_id, attempt)
);
CREATE INDEX IF NOT EXISTS ix_runs_campaign ON runs(campaign_id);

CREATE TABLE IF NOT EXISTS results (
  result_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  evaluator_id TEXT NOT NULL,
  dimension TEXT NOT NULL,
  control_state TEXT NOT NULL,
  status TEXT NOT NULL,
  json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_results_run ON results(run_id);

CREATE TABLE IF NOT EXISTS prices (
  price_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model_id TEXT NOT NULL,
  valid_from TEXT NOT NULL,
  valid_to TEXT,
  json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_prices_lookup ON prices(provider, model_id, valid_from);

CREATE TABLE IF NOT EXISTS scorecards (
  scorecard_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
  ticket_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  status TEXT NOT NULL,
  json TEXT NOT NULL
);

-- Append-only at the logical level: the code base contains no UPDATE/DELETE on this table.
CREATE TABLE IF NOT EXISTS audit_events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  timestamp TEXT NOT NULL,
  event_type TEXT NOT NULL,
  project_id TEXT,
  campaign_id TEXT,
  run_id TEXT,
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL,
  json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_campaign ON audit_events(campaign_id, sequence);
