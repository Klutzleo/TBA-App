-- Migration 001: Create Parties Table for Tab System
-- Phase 2d: Campaign tab system (Story, OOC, Standard, Whisper tabs)
--
-- Purpose: Store party/channel information for organizing campaign chat
-- Each campaign can have multiple parties (tabs), but only one 'story' and one 'ooc' per campaign

CREATE TABLE IF NOT EXISTS parties (
    id VARCHAR PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),  -- UUID-like string for SQLite compatibility
    campaign_id VARCHAR NOT NULL,  -- References campaigns.id (future table)
    name VARCHAR(100) NOT NULL,
    party_type VARCHAR(20) NOT NULL CHECK (party_type IN ('story', 'ooc', 'standard', 'whisper')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,  -- Whether this party/tab is currently active
    archived_at TIMESTAMP NULL,  -- When the party was archived (NULL = active)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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

-- Add comments for documentation (PostgreSQL only, ignored by SQLite)
-- COMMENT ON TABLE parties IS 'Chat channels/tabs within a campaign (Story, OOC, Whispers, etc.)';
-- COMMENT ON COLUMN parties.party_type IS 'Type of party: story (main IC), ooc (out-of-character), standard (custom channel), whisper (private DM)';
-- COMMENT ON COLUMN parties.is_active IS 'Whether this party tab is currently displayed to users';
-- COMMENT ON COLUMN parties.archived_at IS 'Timestamp when party was archived (soft delete)';

-- Migration complete
SELECT 'Migration 001: Parties table created successfully' AS status;
