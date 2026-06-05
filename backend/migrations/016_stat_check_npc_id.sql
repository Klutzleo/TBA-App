-- Migration 016: Add missing npc_id column to stat_check_requests
-- The table was created before this column was added to 015, so IF NOT EXISTS skipped it.

ALTER TABLE stat_check_requests
  ADD COLUMN IF NOT EXISTS npc_id UUID REFERENCES characters(id) ON DELETE SET NULL;
