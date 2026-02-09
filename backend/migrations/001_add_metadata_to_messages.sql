-- Add metadata JSON column to messages table for storing dice roll breakdowns and other structured data

-- Add metadata column (if it doesn't exist)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE messages ADD COLUMN metadata JSON;
    END IF;
END $$;

-- Add index for querying metadata (optional, but helpful for performance)
CREATE INDEX IF NOT EXISTS idx_messages_metadata ON messages USING gin (metadata);
