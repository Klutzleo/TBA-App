-- Migration 005: Update Messages Table (PostgreSQL)
-- Phase 2d: Add party_id to messages for tab-based chat routing
-- Uses VARCHAR for IDs to match existing schema

-- Create messages table if it doesn't exist
CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    campaign_id VARCHAR(36) NOT NULL,
    sender_id VARCHAR(36) NOT NULL,
    sender_name VARCHAR(100) NOT NULL,
    message_type VARCHAR(20) NOT NULL DEFAULT 'chat',
    mode VARCHAR(10) NULL,
    content TEXT NOT NULL,
    attachment_url VARCHAR(500) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add party_id column to messages table (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='messages' AND column_name='party_id'
    ) THEN
        ALTER TABLE messages ADD COLUMN party_id VARCHAR(36) NULL;
    END IF;
END $$;

-- Add foreign key constraint (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_messages_party' AND table_name = 'messages'
    ) THEN
        ALTER TABLE messages ADD CONSTRAINT fk_messages_party
            FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_messages_party_id ON messages(party_id);
CREATE INDEX IF NOT EXISTS idx_messages_campaign_party ON messages(campaign_id, party_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- Add comments
COMMENT ON COLUMN messages.party_id IS 'References parties.id - which tab/channel this message belongs to';
COMMENT ON COLUMN messages.message_type IS 'Message category: chat, combat, system, narration';
COMMENT ON COLUMN messages.mode IS 'Chat mode: IC (in-character) or OOC (out-of-character)';

SELECT 'Migration 005: Messages table updated with party_id column' AS status;
