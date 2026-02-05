-- Migration 002: Create Party Members Table (PostgreSQL)
-- Phase 2d: Track which characters belong to which parties/tabs
-- Uses VARCHAR for IDs to match existing schema

CREATE TABLE IF NOT EXISTS party_members (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    party_id VARCHAR(36) NOT NULL,
    character_id VARCHAR(36) NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at TIMESTAMPTZ NULL,
    CONSTRAINT fk_party_members_party FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE CASCADE,
    CONSTRAINT fk_party_members_character FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_party_members_party_id ON party_members(party_id);
CREATE INDEX IF NOT EXISTS idx_party_members_character_id ON party_members(character_id);
CREATE INDEX IF NOT EXISTS idx_party_members_active ON party_members(left_at) WHERE left_at IS NULL;

-- Create unique constraint: A character can only be in a party once at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_party_members_active_unique
    ON party_members(party_id, character_id)
    WHERE left_at IS NULL;

-- Add comments for documentation
COMMENT ON TABLE party_members IS 'Join table: tracks which characters are in which parties';
COMMENT ON COLUMN party_members.joined_at IS 'When the character joined this party';
COMMENT ON COLUMN party_members.left_at IS 'When the character left this party (NULL = still active member)';

SELECT 'Migration 002: Party members table created successfully' AS status;
