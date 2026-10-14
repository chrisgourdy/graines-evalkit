-- 0003 continuous improvement: ticket fingerprints, learnings, experiments
ALTER TABLE tickets ADD COLUMN fingerprint TEXT;
ALTER TABLE tickets ADD COLUMN agent_id TEXT;
CREATE INDEX IF NOT EXISTS ix_tickets_fingerprint ON tickets(project_id, fingerprint);

CREATE TABLE IF NOT EXISTS learnings (
  learning_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL,
  status TEXT NOT NULL,
  json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_learnings_project ON learnings(project_id, status);

CREATE TABLE IF NOT EXISTS experiments (
  experiment_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  project_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  ticket_id TEXT,
  status TEXT NOT NULL,
  json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_experiments_project ON experiments(project_id, agent_id);
