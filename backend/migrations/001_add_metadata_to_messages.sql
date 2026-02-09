-- Add extra_data JSON column to messages table for storing dice roll breakdowns and other structured data
-- (Note: 'metadata' is reserved by SQLAlchemy, so we use 'extra_data' instead)

-- Add extra_data column (if it doesn't exist)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'extra_data'
    ) THEN
        ALTER TABLE messages ADD COLUMN extra_data JSON;
    END IF;
END $$;

-- Add index for querying extra_data (optional, but helpful for performance)
CREATE INDEX IF NOT EXISTS idx_messages_extra_data ON messages USING gin (extra_data);
