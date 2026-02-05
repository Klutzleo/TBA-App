-- Fix the campaign trigger to use NULL for story_weaver_id in parties
-- This corrects the issue where the trigger was trying to insert NEW.story_weaver_id (which is NULL)

CREATE OR REPLACE FUNCTION create_default_campaign_channels()
RETURNS TRIGGER AS $$
BEGIN
    -- Create Story channel (story_weaver_id is NULL - SW is campaign-level, not channel-level)
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
        NULL,  -- Fixed: was NEW.story_weaver_id, but SW is campaign-level
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
        NULL,  -- Fixed: was NEW.story_weaver_id, but SW is campaign-level
        NEW.created_by_id,
        TRUE
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

SELECT 'Migration 009 completed: Fixed campaign trigger to use NULL for story_weaver_id' AS status;
