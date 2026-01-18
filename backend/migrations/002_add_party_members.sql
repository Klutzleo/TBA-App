-- Migration 002: Create Party Members Table
-- Phase 2d: Track which characters belong to which parties/tabs
--
-- Purpose: Join table between characters and parties
-- Tracks when characters join/leave parties, enabling dynamic party composition

CREATE TABLE IF NOT EXISTS party_members (
    id VARCHAR PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),  -- UUID-like string
    party_id VARCHAR NOT NULL,
    character_id VARCHAR NOT NULL,
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP NULL,  -- NULL = still in party, timestamp = when they left
    FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_party_members_party_id ON party_members(party_id);
CREATE INDEX IF NOT EXISTS idx_party_members_character_id ON party_members(character_id);
CREATE INDEX IF NOT EXISTS idx_party_members_active ON party_members(left_at) WHERE left_at IS NULL;

-- Create unique constraint: A character can only be in a party once at a time
-- (They can rejoin after leaving, but not have duplicate active memberships)
CREATE UNIQUE INDEX IF NOT EXISTS idx_party_members_active_unique
    ON party_members(party_id, character_id)
    WHERE left_at IS NULL;

-- Add comments for documentation (PostgreSQL only)
-- COMMENT ON TABLE party_members IS 'Join table: tracks which characters are in which parties';
-- COMMENT ON COLUMN party_members.joined_at IS 'When the character joined this party';
-- COMMENT ON COLUMN party_members.left_at IS 'When the character left this party (NULL = still active member)';

-- Migration complete
SELECT 'Migration 002: Party members table created successfully' AS status;
