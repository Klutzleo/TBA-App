-- Migration 000: Cleanup Failed SQLite Migration (PostgreSQL)
-- Run this FIRST to clean up any partially created tables from the failed migration
--
-- This script safely drops tables/columns that may have been partially created
-- when the SQLite-syntax migrations failed on PostgreSQL.

-- Drop triggers first (if they exist)
DROP TRIGGER IF EXISTS trigger_parties_updated_at ON parties;
DROP TRIGGER IF EXISTS trigger_abilities_updated_at ON abilities;

-- Drop functions (if they exist)
DROP FUNCTION IF EXISTS update_parties_updated_at();
DROP FUNCTION IF EXISTS update_abilities_updated_at();

-- Drop indexes (if they exist)
DROP INDEX IF EXISTS idx_parties_campaign_id;
DROP INDEX IF EXISTS idx_parties_type;
DROP INDEX IF EXISTS idx_parties_active;
DROP INDEX IF EXISTS idx_parties_one_story_per_campaign;
DROP INDEX IF EXISTS idx_parties_one_ooc_per_campaign;

DROP INDEX IF EXISTS idx_party_members_party_id;
DROP INDEX IF EXISTS idx_party_members_character_id;
DROP INDEX IF EXISTS idx_party_members_active;
DROP INDEX IF EXISTS idx_party_members_active_unique;

DROP INDEX IF EXISTS idx_abilities_character_id;
DROP INDEX IF EXISTS idx_abilities_slot;
DROP INDEX IF EXISTS idx_abilities_character_slot;
DROP INDEX IF EXISTS idx_abilities_character_macro;

DROP INDEX IF EXISTS idx_messages_party_id;
DROP INDEX IF EXISTS idx_messages_campaign_party;
DROP INDEX IF EXISTS idx_messages_created_at;

DROP INDEX IF EXISTS idx_characters_status;

-- Drop tables in correct order (respecting foreign keys)
DROP TABLE IF EXISTS party_members CASCADE;
DROP TABLE IF EXISTS abilities CASCADE;
DROP TABLE IF EXISTS parties CASCADE;

-- Remove columns from characters table (if they were added)
DO $$
BEGIN
    -- Drop constraint first if it exists
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'check_character_status' AND table_name = 'characters'
    ) THEN
        ALTER TABLE characters DROP CONSTRAINT check_character_status;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='notes') THEN
        ALTER TABLE characters DROP COLUMN notes;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='max_uses_per_encounter') THEN
        ALTER TABLE characters DROP COLUMN max_uses_per_encounter;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='current_uses') THEN
        ALTER TABLE characters DROP COLUMN current_uses;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='weapon_bonus') THEN
        ALTER TABLE characters DROP COLUMN weapon_bonus;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='armor_bonus') THEN
        ALTER TABLE characters DROP COLUMN armor_bonus;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='times_called') THEN
        ALTER TABLE characters DROP COLUMN times_called;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='is_called') THEN
        ALTER TABLE characters DROP COLUMN is_called;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='status') THEN
        ALTER TABLE characters DROP COLUMN status;
    END IF;
END $$;

-- Remove party_id from messages (if it was added)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_messages_party' AND table_name = 'messages'
    ) THEN
        ALTER TABLE messages DROP CONSTRAINT fk_messages_party;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='messages' AND column_name='party_id') THEN
        ALTER TABLE messages DROP COLUMN party_id;
    END IF;
END $$;

-- Cleanup complete
SELECT 'Migration 000: Cleanup complete - ready for fresh PostgreSQL migrations' AS status;
