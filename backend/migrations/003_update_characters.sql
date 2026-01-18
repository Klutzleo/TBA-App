-- Migration 003: Update Characters Table
-- Phase 2d: Add character notes, status tracking, and equipment bonuses
--
-- Purpose: Enhance character model with:
-- - Notes field for character backstory/personality
-- - Uses per encounter (for limited-use abilities)
-- - Weapon/armor bonuses (separate from equipment objects)
-- - Status tracking (active/unconscious/dead)
-- - Called status (for summoned characters/familiars)

-- Add notes column
ALTER TABLE characters ADD COLUMN IF NOT EXISTS notes TEXT NULL;

-- Add uses per encounter (for abilities with limited uses)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS max_uses_per_encounter INTEGER NOT NULL DEFAULT 3;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_uses INTEGER NOT NULL DEFAULT 3;

-- Add weapon and armor bonuses (separate from equipment JSON for quick access)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS weapon_bonus INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS armor_bonus INTEGER NOT NULL DEFAULT 0;

-- Add "called" status (for summoned creatures/familiars)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS times_called INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS is_called BOOLEAN NOT NULL DEFAULT FALSE;

-- Add character status (active, unconscious, dead)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active';

-- Note: SQLite doesn't support CHECK constraints in ALTER TABLE, so we add it conditionally
-- For PostgreSQL, you would use:
-- ALTER TABLE characters ADD CONSTRAINT check_character_status
--     CHECK (status IN ('active', 'unconscious', 'dead'));

-- For SQLite compatibility, we recreate the table with the constraint if needed
-- This is handled by the Python migration script that reads these SQL files

-- Add index on status for filtering
CREATE INDEX IF NOT EXISTS idx_characters_status ON characters(status);

-- Add comments for documentation (PostgreSQL only)
-- COMMENT ON COLUMN characters.notes IS 'Character backstory, personality notes, GM notes';
-- COMMENT ON COLUMN characters.max_uses_per_encounter IS 'Maximum number of times limited abilities can be used per encounter';
-- COMMENT ON COLUMN characters.current_uses IS 'Remaining uses for limited abilities in current encounter';
-- COMMENT ON COLUMN characters.weapon_bonus IS 'Weapon attack bonus (from equipped weapon)';
-- COMMENT ON COLUMN characters.armor_bonus IS 'Armor defense bonus (from equipped armor)';
-- COMMENT ON COLUMN characters.times_called IS 'Number of times this character/summon has been called';
-- COMMENT ON COLUMN characters.is_called IS 'Whether this character is currently summoned/called';
-- COMMENT ON COLUMN characters.status IS 'Character status: active, unconscious, or dead';

-- Migration complete
SELECT 'Migration 003: Characters table updated successfully' AS status;
