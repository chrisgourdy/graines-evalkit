-- 0002 TOKEN_METER usage records, COST_CONTROLLER budgets and reservations
CREATE TABLE IF NOT EXISTS usage_records (
  usage_id TEXT PRIMARY KEY,
  recorded_at TEXT NOT NULL,
  organization_id TEXT,
  project_id TEXT NOT NULL,
  agent_id TEXT,
  agent_version TEXT,
  campaign_id TEXT,
  scenario_id TEXT,
  run_id TEXT,
  step_index INTEGER,
  call_id TEXT,
  evaluator_id TEXT,
  period TEXT,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  source TEXT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cached_input_tokens INTEGER,
  cache_creation_tokens INTEGER,
  reasoning_tokens INTEGER,
  billable_total INTEGER,
  cost_status TEXT,
  cost_amount TEXT,
  cost_currency TEXT,
  price_id TEXT,
  json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_usage_campaign ON usage_records(campaign_id);
CREATE INDEX IF NOT EXISTS ix_usage_project_period ON usage_records(project_id, period);
CREATE INDEX IF NOT EXISTS ix_usage_agent ON usage_records(project_id, agent_id, agent_version);

CREATE TABLE IF NOT EXISTS budgets (
  budget_id TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  scope_ref TEXT NOT NULL,
  currency TEXT NOT NULL,
  max_cost REAL,
  max_tokens INTEGER,
  json TEXT NOT NULL,
  UNIQUE (scope, scope_ref)
);

-- One row per (reservation, budget). Spent = settled observed + open reserved.
CREATE TABLE IF NOT EXISTS reservations (
  reservation_id TEXT NOT NULL,
  budget_id TEXT NOT NULL,
  campaign_id TEXT NOT NULL,
  run_id TEXT,
  created_at TEXT NOT NULL,
  reserved_cost REAL NOT NULL,
  reserved_tokens INTEGER,
  settled INTEGER NOT NULL DEFAULT 0,
  released INTEGER NOT NULL DEFAULT 0,
  observed_cost REAL,
  observed_tokens INTEGER,
  PRIMARY KEY (reservation_id, budget_id)
);
CREATE INDEX IF NOT EXISTS ix_reservations_budget ON reservations(budget_id, released);
CREATE INDEX IF NOT EXISTS ix_reservations_campaign ON reservations(campaign_id);
