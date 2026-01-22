-- Migration 006: Add in_calling flag for The Calling feature
-- When a character reaches -10 DP, they enter The Calling state
-- This flag tracks whether they are currently in that state

ALTER TABLE characters ADD COLUMN IF NOT EXISTS in_calling BOOLEAN DEFAULT FALSE;

-- Index for quick lookup of characters in The Calling state
CREATE INDEX IF NOT EXISTS idx_characters_in_calling ON characters(in_calling) WHERE in_calling = TRUE;
