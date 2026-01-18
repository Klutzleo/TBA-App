-- Migration 003: Update Characters Table (PostgreSQL)
-- Phase 2d: Add character notes, status tracking, and equipment bonuses
--
-- Purpose: Enhance character model with:
-- - Notes field for character backstory/personality
-- - Uses per encounter (for limited-use abilities)
-- - Weapon/armor bonuses (separate from equipment objects)
-- - Status tracking (active/unconscious/dead)
-- - Called status (for summoned characters/familiars)

-- Add notes column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='characters' AND column_name='notes'
    ) THEN
        ALTER TABLE characters ADD COLUMN notes TEXT NULL;
    END IF;
END $$;

-- Add uses per encounter (for abilities with limited uses)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='characters' AND column_name='max_uses_per_encounter'
    ) THEN
        ALTER TABLE characters ADD COLUMN max_uses_per_encounter INTEGER NOT NULL DEFAULT 3;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='characters' AND column_name='current_uses'
    ) THEN
        ALTER TABLE characters ADD COLUMN current_uses INTEGER NOT NULL DEFAULT 3;
    END IF;
END $$;

-- Add weapon and armor bonuses (separate from equipment JSON for quick access)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='characters' AND column_name='weapon_bonus'
    ) THEN
        ALTER TABLE characters ADD COLUMN weapon_bonus INTEGER NOT NULL DEFAULT 0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='characters' AND column_name='armor_bonus'
    ) THEN
        ALTER TABLE characters ADD COLUMN armor_bonus INTEGER NOT NULL DEFAULT 0;
    END IF;
END $$;

-- Add "called" status (for summoned creatures/familiars)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='characters' AND column_name='times_called'
    ) THEN
        ALTER TABLE characters ADD COLUMN times_called INTEGER NOT NULL DEFAULT 0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='characters' AND column_name='is_called'
    ) THEN
        ALTER TABLE characters ADD COLUMN is_called BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END $$;

-- Add character status (active, unconscious, dead)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='characters' AND column_name='status'
    ) THEN
        ALTER TABLE characters ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';
    END IF;
END $$;

-- Add CHECK constraint for status (PostgreSQL supports this)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.constraint_column_usage
        WHERE constraint_name = 'check_character_status'
    ) THEN
        ALTER TABLE characters ADD CONSTRAINT check_character_status
            CHECK (status IN ('active', 'unconscious', 'dead'));
    END IF;
END $$;

-- Add index on status for filtering
CREATE INDEX IF NOT EXISTS idx_characters_status ON characters(status);

-- Add comments for documentation
COMMENT ON COLUMN characters.notes IS 'Character backstory, personality notes, GM notes';
COMMENT ON COLUMN characters.max_uses_per_encounter IS 'Maximum number of times limited abilities can be used per encounter';
COMMENT ON COLUMN characters.current_uses IS 'Remaining uses for limited abilities in current encounter';
COMMENT ON COLUMN characters.weapon_bonus IS 'Weapon attack bonus (from equipped weapon)';
COMMENT ON COLUMN characters.armor_bonus IS 'Armor defense bonus (from equipped armor)';
COMMENT ON COLUMN characters.times_called IS 'Number of times this character/summon has been called';
COMMENT ON COLUMN characters.is_called IS 'Whether this character is currently summoned/called';
COMMENT ON COLUMN characters.status IS 'Character status: active, unconscious, or dead';

-- Migration complete
SELECT 'Migration 003: Characters table updated successfully' AS status;
