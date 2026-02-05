-- Migration 001: Update Parties Table for Tab System (PostgreSQL)
-- Phase 2d: Add tab system columns to existing parties table
-- The parties table already exists with: id, name, description, session_id, story_weaver_id, created_by_id, created_at, updated_at

-- Add campaign_id column (nullable for existing rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='parties' AND column_name='campaign_id'
    ) THEN
        ALTER TABLE parties ADD COLUMN campaign_id VARCHAR(36) NULL;
    END IF;
END $$;

-- Add party_type column with default 'standard'
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='parties' AND column_name='party_type'
    ) THEN
        ALTER TABLE parties ADD COLUMN party_type VARCHAR(20) NOT NULL DEFAULT 'standard';
        -- Add CHECK constraint
        ALTER TABLE parties ADD CONSTRAINT check_party_type
            CHECK (party_type IN ('story', 'ooc', 'standard', 'whisper'));
    END IF;
END $$;

-- Add is_active column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='parties' AND column_name='is_active'
    ) THEN
        ALTER TABLE parties ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
    END IF;
END $$;

-- Add archived_at column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='parties' AND column_name='archived_at'
    ) THEN
        ALTER TABLE parties ADD COLUMN archived_at TIMESTAMPTZ NULL;
    END IF;
END $$;

-- Create indexes (only if columns exist now)
CREATE INDEX IF NOT EXISTS idx_parties_campaign_id ON parties(campaign_id);
CREATE INDEX IF NOT EXISTS idx_parties_type ON parties(party_type);
CREATE INDEX IF NOT EXISTS idx_parties_active ON parties(is_active);

-- Create unique constraints for story/ooc per campaign (only if campaign_id exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='parties' AND column_name='campaign_id'
    ) THEN
        -- Drop existing indexes if they exist (to recreate)
        DROP INDEX IF EXISTS idx_parties_one_story_per_campaign;
        DROP INDEX IF EXISTS idx_parties_one_ooc_per_campaign;

        -- Create unique partial indexes
        CREATE UNIQUE INDEX idx_parties_one_story_per_campaign
            ON parties(campaign_id, party_type)
            WHERE party_type = 'story' AND campaign_id IS NOT NULL;

        CREATE UNIQUE INDEX idx_parties_one_ooc_per_campaign
            ON parties(campaign_id, party_type)
            WHERE party_type = 'ooc' AND campaign_id IS NOT NULL;
    END IF;
END $$;

-- Add comments
COMMENT ON COLUMN parties.campaign_id IS 'Campaign this party belongs to (NULL for legacy parties)';
COMMENT ON COLUMN parties.party_type IS 'Type: story (main IC), ooc (out-of-character), standard (custom), whisper (DM)';
COMMENT ON COLUMN parties.is_active IS 'Whether this party tab is currently displayed';
COMMENT ON COLUMN parties.archived_at IS 'Timestamp when archived (soft delete)';

-- Create/update trigger for updated_at
CREATE OR REPLACE FUNCTION update_parties_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_parties_updated_at ON parties;
CREATE TRIGGER trigger_parties_updated_at
    BEFORE UPDATE ON parties
    FOR EACH ROW
    EXECUTE FUNCTION update_parties_updated_at();

SELECT 'Migration 001: Parties table updated with tab system columns' AS status;
