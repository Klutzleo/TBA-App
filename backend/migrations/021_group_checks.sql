-- Migration 021: Group checks — multi-target Stat Check + Env Check
-- Additive only. All ADD COLUMN IF NOT EXISTS — safe to re-run.

ALTER TABLE stat_check_requests
  ADD COLUMN IF NOT EXISTS kind         VARCHAR(8) NOT NULL DEFAULT 'stat',   -- stat | env
  ADD COLUMN IF NOT EXISTS tier         SMALLINT,                             -- env only, 1-5
  ADD COLUMN IF NOT EXISTS damage_dealt INTEGER,                              -- env only, on resolve
  ADD COLUMN IF NOT EXISTS group_id     UUID,                                 -- shared per multi-target send
  ADD COLUMN IF NOT EXISTS sw_user_id   UUID;                                 -- SW who created it

CREATE INDEX IF NOT EXISTS idx_stat_check_group ON stat_check_requests(group_id);

ALTER TABLE user_stats
  ADD COLUMN IF NOT EXISTS env_damage_used   INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS env_tiers_mask    INTEGER NOT NULL DEFAULT 0,   -- bits 1-5
  ADD COLUMN IF NOT EXISTS group_checks_sent INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS group_wipes       INTEGER NOT NULL DEFAULT 0,   -- group of 2+, all failed
  ADD COLUMN IF NOT EXISTS group_flawless    INTEGER NOT NULL DEFAULT 0;   -- group of 2+, all passed
