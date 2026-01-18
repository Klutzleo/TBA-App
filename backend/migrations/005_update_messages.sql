-- Migration 005: Update Messages Table
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
    id VARCHAR PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    campaign_id VARCHAR NOT NULL,
    sender_id VARCHAR NOT NULL,  -- Character or user ID
    sender_name VARCHAR(100) NOT NULL,
    message_type VARCHAR(20) NOT NULL DEFAULT 'chat',  -- chat, combat, system, narration
    mode VARCHAR(10) NULL,  -- IC, OOC (only for chat messages)
    content TEXT NOT NULL,
    attachment_url VARCHAR(500) NULL,  -- Image/file attachment
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add party_id column to messages table
ALTER TABLE messages ADD COLUMN IF NOT EXISTS party_id VARCHAR NULL;

-- Add foreign key constraint (with ON DELETE SET NULL for safety)
-- Note: SQLite has limited ALTER TABLE support, so we can't add FK constraints after table creation
-- This would work in PostgreSQL:
-- ALTER TABLE messages ADD CONSTRAINT fk_messages_party
--     FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE SET NULL;

-- For SQLite, we document this as a soft foreign key and enforce in application code
-- Future migrations can recreate the table with the FK if needed

-- Create index for efficient party-based message queries
CREATE INDEX IF NOT EXISTS idx_messages_party_id ON messages(party_id);

-- Create index for campaign + party queries (common query pattern)
CREATE INDEX IF NOT EXISTS idx_messages_campaign_party ON messages(campaign_id, party_id);

-- Add index on timestamp for chronological ordering
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- Add comments for documentation (PostgreSQL only)
-- COMMENT ON COLUMN messages.party_id IS 'References parties.id - which tab/channel this message belongs to';
-- COMMENT ON COLUMN messages.message_type IS 'Message category: chat, combat, system, narration';
-- COMMENT ON COLUMN messages.mode IS 'Chat mode: IC (in-character) or OOC (out-of-character)';

-- Migration complete
SELECT 'Migration 005: Messages table updated with party_id column' AS status;
SELECT 'NOTE: Run data migration script separately to move existing messages to parties' AS reminder;
