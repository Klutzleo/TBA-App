-- Migration 005: Update Messages Table (PostgreSQL)
-- Phase 2d: Add party_id to messages for tab-based chat routing
--
-- Purpose: Associate messages with specific party tabs (Story, OOC, Whispers, etc.)
-- This enables tab-based chat filtering and organization
--
-- NOTE: This migration ONLY adds the column and foreign key.
-- Data migration (moving existing messages to parties) will be handled separately
-- by a Python script to avoid data loss and handle edge cases.

-- Check if messages table exists first (it may not exist in new installations)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL,
    sender_id UUID NOT NULL,  -- Character or user ID
    sender_name VARCHAR(100) NOT NULL,
    message_type VARCHAR(20) NOT NULL DEFAULT 'chat',  -- chat, combat, system, narration
    mode VARCHAR(10) NULL,  -- IC, OOC (only for chat messages)
    content TEXT NOT NULL,
    attachment_url VARCHAR(500) NULL,  -- Image/file attachment
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add party_id column to messages table (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='messages' AND column_name='party_id'
    ) THEN
        ALTER TABLE messages ADD COLUMN party_id UUID NULL;
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

-- Create index for efficient party-based message queries
CREATE INDEX IF NOT EXISTS idx_messages_party_id ON messages(party_id);

-- Create index for campaign + party queries (common query pattern)
CREATE INDEX IF NOT EXISTS idx_messages_campaign_party ON messages(campaign_id, party_id);

-- Add index on timestamp for chronological ordering
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- Add comments for documentation
COMMENT ON COLUMN messages.party_id IS 'References parties.id - which tab/channel this message belongs to';
COMMENT ON COLUMN messages.message_type IS 'Message category: chat, combat, system, narration';
COMMENT ON COLUMN messages.mode IS 'Chat mode: IC (in-character) or OOC (out-of-character)';

-- Migration complete
SELECT 'Migration 005: Messages table updated with party_id column' AS status;
