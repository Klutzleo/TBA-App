-- Migration 000: Cleanup Failed Migration (PostgreSQL)
-- Run this to clean up any partially created tables from failed migrations

-- Drop triggers first
DROP TRIGGER IF EXISTS trigger_parties_updated_at ON parties;
DROP TRIGGER IF EXISTS trigger_abilities_updated_at ON abilities;

-- Drop functions
DROP FUNCTION IF EXISTS update_parties_updated_at();
DROP FUNCTION IF EXISTS update_abilities_updated_at();

-- Drop all indexes
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

-- Drop tables (CASCADE handles foreign keys)
DROP TABLE IF EXISTS party_members CASCADE;
DROP TABLE IF EXISTS abilities CASCADE;
DROP TABLE IF EXISTS parties CASCADE;

-- Remove columns from characters table
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'check_character_status' AND table_name = 'characters') THEN
        ALTER TABLE characters DROP CONSTRAINT check_character_status;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='notes') THEN
        ALTER TABLE characters DROP COLUMN notes;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='max_uses_per_encounter') THEN
        ALTER TABLE characters DROP COLUMN max_uses_per_encounter;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='current_uses') THEN
        ALTER TABLE characters DROP COLUMN current_uses;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='weapon_bonus') THEN
        ALTER TABLE characters DROP COLUMN weapon_bonus;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='armor_bonus') THEN
        ALTER TABLE characters DROP COLUMN armor_bonus;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='times_called') THEN
        ALTER TABLE characters DROP COLUMN times_called;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='is_called') THEN
        ALTER TABLE characters DROP COLUMN is_called;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='characters' AND column_name='status') THEN
        ALTER TABLE characters DROP COLUMN status;
    END IF;
END $$;

-- Remove party_id from messages
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'fk_messages_party' AND table_name = 'messages') THEN
        ALTER TABLE messages DROP CONSTRAINT fk_messages_party;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='messages' AND column_name='party_id') THEN
        ALTER TABLE messages DROP COLUMN party_id;
    END IF;
END $$;

SELECT 'Migration 000: Cleanup complete - ready for fresh migrations' AS status;
