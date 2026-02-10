-- Migration: Add ability usage tracking
-- Adds max_uses and uses_remaining to abilities table
-- Formula: 3 uses per encounter per character level

-- Add max_uses column (total charges per encounter based on level)
ALTER TABLE abilities
ADD COLUMN IF NOT EXISTS max_uses INTEGER NOT NULL DEFAULT 3;

-- Add uses_remaining column (current charges in this encounter)
ALTER TABLE abilities
ADD COLUMN IF NOT EXISTS uses_remaining INTEGER NOT NULL DEFAULT 3;

-- Set initial values based on character level
-- Formula: 3 * character_level
UPDATE abilities a
SET max_uses = 3 * (
    SELECT COALESCE(c.level, 1)
    FROM characters c
    WHERE c.id = a.character_id
),
uses_remaining = 3 * (
    SELECT COALESCE(c.level, 1)
    FROM characters c
    WHERE c.id = a.character_id
);
