-- Migration 007: Create Campaigns and Restructure for Channel Architecture
-- Creates the campaigns table and properly structures parties as communication channels

-- =====================================================================
-- 1. Create campaigns table
-- =====================================================================
CREATE TABLE IF NOT EXISTS campaigns (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    story_weaver_id VARCHAR(36) REFERENCES characters(id) ON DELETE SET NULL,
    created_by_id VARCHAR(36) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_campaigns_story_weaver ON campaigns(story_weaver_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_created_by ON campaigns(created_by_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_active ON campaigns(is_active);

COMMENT ON TABLE campaigns IS 'Game campaigns - the container for all players and communication channels';
COMMENT ON COLUMN campaigns.story_weaver_id IS 'The Story Weaver (GM) for this campaign';
COMMENT ON COLUMN campaigns.created_by_id IS 'User ID who created this campaign';

-- =====================================================================
-- 2. Update parties table to be proper campaign channels
-- =====================================================================
-- Drop the old FK constraint if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'parties_campaign_id_fkey' AND table_name = 'parties'
    ) THEN
        ALTER TABLE parties DROP CONSTRAINT parties_campaign_id_fkey;
    END IF;
END $$;

-- Add proper FK constraint to campaigns
DO $$
BEGIN
    -- Only add if the constraint doesn't already exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_parties_campaign' AND table_name = 'parties'
    ) THEN
        ALTER TABLE parties
        ADD CONSTRAINT fk_parties_campaign
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Update party_type to support all channel types
DO $$
BEGIN
    -- Drop old constraint if exists
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'check_party_type' AND table_name = 'parties'
    ) THEN
        ALTER TABLE parties DROP CONSTRAINT check_party_type;
    END IF;

    -- Add new constraint with all channel types
    ALTER TABLE parties ADD CONSTRAINT check_party_type
        CHECK (party_type IN ('story', 'ooc', 'whisper', 'spectator', 'split_group'));
END $$;

-- Ensure campaign_id is NOT NULL for new records (existing NULL records are OK)
DO $$
BEGIN
    -- We'll make it nullable for now to allow gradual migration
    -- In production, you'd make it NOT NULL after backfilling data
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='parties' AND column_name='campaign_id' AND is_nullable='YES'
    ) THEN
        -- Keep it nullable for now, comment explains why
        NULL; -- Do nothing
    END IF;
END $$;

COMMENT ON TABLE parties IS 'Communication channels within campaigns (Story, OOC, Whisper, Split Groups, etc.)';
COMMENT ON COLUMN parties.campaign_id IS 'The campaign this channel belongs to';
COMMENT ON COLUMN parties.party_type IS 'Channel type: story (main), ooc (out-of-character), whisper (DM), spectator (observers), split_group (when party splits)';
COMMENT ON COLUMN parties.story_weaver_id IS 'Deprecated - use campaigns.story_weaver_id instead';

-- =====================================================================
-- 3. Create function to auto-create Story and OOC channels for new campaigns
-- =====================================================================
CREATE OR REPLACE FUNCTION create_default_campaign_channels()
RETURNS TRIGGER AS $$
BEGIN
    -- Create Story channel
    INSERT INTO parties (
        id,
        campaign_id,
        name,
        description,
        party_type,
        story_weaver_id,
        created_by_id,
        is_active
    ) VALUES (
        gen_random_uuid()::text,
        NEW.id,
        NEW.name || ' - Story',
        'Main story channel for ' || NEW.name,
        'story',
        NEW.story_weaver_id,
        NEW.created_by_id,
        TRUE
    );

    -- Create OOC channel
    INSERT INTO parties (
        id,
        campaign_id,
        name,
        description,
        party_type,
        story_weaver_id,
        created_by_id,
        is_active
    ) VALUES (
        gen_random_uuid()::text,
        NEW.id,
        NEW.name || ' - OOC',
        'Out-of-character chat for ' || NEW.name,
        'ooc',
        NEW.story_weaver_id,
        NEW.created_by_id,
        TRUE
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-create channels
DROP TRIGGER IF EXISTS trigger_create_campaign_channels ON campaigns;
CREATE TRIGGER trigger_create_campaign_channels
    AFTER INSERT ON campaigns
    FOR EACH ROW
    EXECUTE FUNCTION create_default_campaign_channels();

-- =====================================================================
-- 4. Create updated_at trigger for campaigns
-- =====================================================================
CREATE OR REPLACE FUNCTION update_campaigns_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_campaigns_updated_at ON campaigns;
CREATE TRIGGER trigger_campaigns_updated_at
    BEFORE UPDATE ON campaigns
    FOR EACH ROW
    EXECUTE FUNCTION update_campaigns_updated_at();

-- =====================================================================
-- 5. Create helper view for campaign overview
-- =====================================================================
CREATE OR REPLACE VIEW campaign_overview AS
SELECT
    c.id,
    c.name,
    c.description,
    c.story_weaver_id,
    c.created_by_id,
    c.is_active,
    c.created_at,
    COUNT(DISTINCT pm.character_id) as player_count,
    COUNT(DISTINCT CASE WHEN p.party_type = 'story' THEN p.id END) as story_channels,
    COUNT(DISTINCT CASE WHEN p.party_type = 'ooc' THEN p.id END) as ooc_channels,
    COUNT(DISTINCT CASE WHEN p.party_type = 'whisper' THEN p.id END) as whisper_channels,
    COUNT(DISTINCT CASE WHEN p.party_type = 'split_group' THEN p.id END) as split_group_channels
FROM campaigns c
LEFT JOIN parties p ON p.campaign_id = c.id
LEFT JOIN party_memberships pm ON pm.party_id = p.id
GROUP BY c.id, c.name, c.description, c.story_weaver_id, c.created_by_id, c.is_active, c.created_at;

SELECT '✅ Migration 007: Campaigns and channel architecture created successfully!' AS status;
