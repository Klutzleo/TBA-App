-- Migration 019: Link characters to campaigns
-- Phase 3 Part 3: Add campaign_id column to characters table

-- Add campaign_id column to characters
ALTER TABLE characters ADD COLUMN campaign_id VARCHAR;

-- Add foreign key constraint
ALTER TABLE characters ADD CONSTRAINT fk_characters_campaign
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL;

-- Create index for performance
CREATE INDEX idx_characters_campaign_id ON characters(campaign_id);
