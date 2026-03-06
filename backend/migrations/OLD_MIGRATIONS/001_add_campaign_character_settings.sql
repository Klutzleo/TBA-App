-- Add character creation governance fields to campaigns table
-- This migration adds two new columns without dropping existing data

ALTER TABLE campaigns
ADD COLUMN IF NOT EXISTS character_creation_mode VARCHAR NOT NULL DEFAULT 'open'
CHECK (character_creation_mode IN ('open', 'approval_required', 'sw_only'));

ALTER TABLE campaigns
ADD COLUMN IF NOT EXISTS max_characters_per_player INTEGER NOT NULL DEFAULT 1;
