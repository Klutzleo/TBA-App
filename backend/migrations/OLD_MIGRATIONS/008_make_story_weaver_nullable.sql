-- Make story_weaver_id nullable in parties table
-- This is correct for the architecture: SW is a campaign-level role, not channel-level
ALTER TABLE parties ALTER COLUMN story_weaver_id DROP NOT NULL;

-- Also make campaign fields nullable for bootstrapping
ALTER TABLE campaigns ALTER COLUMN story_weaver_id DROP NOT NULL;
ALTER TABLE campaigns ALTER COLUMN created_by_id DROP NOT NULL;

-- Make character.campaign_id nullable temporarily for bootstrapping
ALTER TABLE characters ALTER COLUMN campaign_id DROP NOT NULL;

-- Update the trigger to use NULL for story_weaver_id in parties (SW is campaign-level, not channel-level)
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
        NULL,  -- Changed from NEW.story_weaver_id - SW is campaign-level
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
        'Out-of-character discussion for ' || NEW.name,
        'ooc',
        NULL,  -- Changed from NEW.story_weaver_id - SW is campaign-level
        NEW.created_by_id,
        TRUE
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

SELECT 'Migration 008 completed: Made story_weaver_id nullable and updated trigger' AS status;
