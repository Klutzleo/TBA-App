-- Migration 001: Create Parties Table for Tab System (PostgreSQL)
-- Phase 2d: Campaign tab system (Story, OOC, Standard, Whisper tabs)
-- Uses VARCHAR for IDs to match existing schema (models.py uses String)

CREATE TABLE IF NOT EXISTS parties (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    campaign_id VARCHAR(36) NOT NULL,
    name VARCHAR(100) NOT NULL,
    party_type VARCHAR(20) NOT NULL CHECK (party_type IN ('story', 'ooc', 'standard', 'whisper')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_parties_campaign_id ON parties(campaign_id);
CREATE INDEX IF NOT EXISTS idx_parties_type ON parties(party_type);
CREATE INDEX IF NOT EXISTS idx_parties_active ON parties(is_active);

-- Create unique constraint: Only one 'story' party per campaign
CREATE UNIQUE INDEX IF NOT EXISTS idx_parties_one_story_per_campaign
    ON parties(campaign_id, party_type)
    WHERE party_type = 'story';

-- Create unique constraint: Only one 'ooc' party per campaign
CREATE UNIQUE INDEX IF NOT EXISTS idx_parties_one_ooc_per_campaign
    ON parties(campaign_id, party_type)
    WHERE party_type = 'ooc';

-- Add comments for documentation
COMMENT ON TABLE parties IS 'Chat channels/tabs within a campaign (Story, OOC, Whispers, etc.)';
COMMENT ON COLUMN parties.party_type IS 'Type of party: story (main IC), ooc (out-of-character), standard (custom channel), whisper (private DM)';
COMMENT ON COLUMN parties.is_active IS 'Whether this party tab is currently displayed to users';
COMMENT ON COLUMN parties.archived_at IS 'Timestamp when party was archived (soft delete)';

-- Create trigger function for updated_at
CREATE OR REPLACE FUNCTION update_parties_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_parties_updated_at ON parties;
CREATE TRIGGER trigger_parties_updated_at
    BEFORE UPDATE ON parties
    FOR EACH ROW
    EXECUTE FUNCTION update_parties_updated_at();

SELECT 'Migration 001: Parties table created successfully' AS status;
