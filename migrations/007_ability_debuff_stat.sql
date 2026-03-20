-- Add debuff_stat column to abilities table
-- Specifies which stat on the TARGET gets penalized when a debuff lands
-- Options: PP, IP, SP, Defense, All
ALTER TABLE abilities ADD COLUMN IF NOT EXISTS debuff_stat VARCHAR(20) DEFAULT NULL;
