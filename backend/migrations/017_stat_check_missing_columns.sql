-- Migration 017: Add all missing columns to stat_check_requests
-- Table predates migration 015 so CREATE TABLE IF NOT EXISTS was a no-op.
-- ADD COLUMN IF NOT EXISTS is idempotent — safe to run multiple times.

ALTER TABLE stat_check_requests
  ADD COLUMN IF NOT EXISTS npc_id           UUID REFERENCES characters(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS mode             VARCHAR(10) NOT NULL DEFAULT 'character',
  ADD COLUMN IF NOT EXISTS difficulty_die   VARCHAR(8),
  ADD COLUMN IF NOT EXISTS difficulty_label VARCHAR(50),
  ADD COLUMN IF NOT EXISTS sw_roll          INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS flavor_text      TEXT,
  ADD COLUMN IF NOT EXISTS bap_granted      BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS hidden           BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS player_roll      INTEGER,
  ADD COLUMN IF NOT EXISTS player_total     INTEGER,
  ADD COLUMN IF NOT EXISTS outcome          VARCHAR(4),
  ADD COLUMN IF NOT EXISTS margin           INTEGER,
  ADD COLUMN IF NOT EXISTS resolved_at      TIMESTAMPTZ;
