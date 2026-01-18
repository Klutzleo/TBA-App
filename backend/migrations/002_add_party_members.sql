-- Migration 002: Create Party Members Table (PostgreSQL)
-- Phase 2d: Track which characters belong to which parties/tabs
--
-- Purpose: Join table between characters and parties
-- Tracks when characters join/leave parties, enabling dynamic party composition

CREATE TABLE IF NOT EXISTS party_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL,
    character_id UUID NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at TIMESTAMPTZ NULL,  -- NULL = still in party, timestamp = when they left
    CONSTRAINT fk_party_members_party FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE CASCADE,
    CONSTRAINT fk_party_members_character FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
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

-- Add comments for documentation
COMMENT ON TABLE party_members IS 'Join table: tracks which characters are in which parties';
COMMENT ON COLUMN party_members.party_id IS 'References parties.id - which party/tab this membership is for';
COMMENT ON COLUMN party_members.character_id IS 'References characters.id - which character is in the party';
COMMENT ON COLUMN party_members.joined_at IS 'When the character joined this party';
COMMENT ON COLUMN party_members.left_at IS 'When the character left this party (NULL = still active member)';

-- Migration complete
SELECT 'Migration 002: Party members table created successfully' AS status;
