-- Add extra_data JSONB column to messages table for storing dice roll breakdowns and other structured data
-- (Note: 'metadata' is reserved by SQLAlchemy, so we use 'extra_data' instead)
-- (Note: Using JSONB instead of JSON for better performance and indexing support)

-- Add extra_data column (if it doesn't exist)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'messages' AND column_name = 'extra_data'
    ) THEN
        ALTER TABLE messages ADD COLUMN extra_data JSONB;
    END IF;
END $$;

-- Add GIN index for querying extra_data (JSONB supports GIN indexes)
CREATE INDEX IF NOT EXISTS idx_messages_extra_data ON messages USING gin (extra_data);
