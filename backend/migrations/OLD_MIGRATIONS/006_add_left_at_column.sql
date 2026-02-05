-- Migration 006: Add left_at column to party_memberships
-- Fix: The table was created as party_memberships but was missing the left_at column

-- Add left_at column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'party_memberships' AND column_name = 'left_at'
    ) THEN
        ALTER TABLE party_memberships ADD COLUMN left_at TIMESTAMPTZ NULL;
        RAISE NOTICE 'Added left_at column to party_memberships';
    ELSE
        RAISE NOTICE 'Column left_at already exists in party_memberships';
    END IF;
END $$;

-- Create index for efficient queries on active memberships
CREATE INDEX IF NOT EXISTS idx_party_memberships_active ON party_memberships(left_at) WHERE left_at IS NULL;

-- Add comment for documentation
COMMENT ON COLUMN party_memberships.left_at IS 'When the character left this party (NULL = still active member)';

SELECT 'Migration 006: Added left_at column to party_memberships' AS status;
