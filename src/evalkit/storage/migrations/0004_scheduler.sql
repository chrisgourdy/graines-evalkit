-- Phase 7: scheduler state (one row per job of a plan; durable across restarts)
CREATE TABLE IF NOT EXISTS schedule_state (
    job_name TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_run_at TEXT,
    last_campaign_id TEXT,
    running_campaign_id TEXT,
    last_good_campaign_id TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    retrofit_day TEXT,
    retrofits_today INTEGER NOT NULL DEFAULT 0,
    last_retrofit_at TEXT,
    paused_reason TEXT,
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_schedule_state_plan ON schedule_state(plan_id);
