-- ================================================================
-- TEMPORARY: Convert campaigns.id from VARCHAR to UUID
-- This allows campaign_memberships FK to work properly
-- TODO: Remove this file after one successful deploy
-- ================================================================

DO $$
BEGIN
    -- Drop the FK constraint from parties (will be recreated with correct type)
    ALTER TABLE parties DROP CONSTRAINT IF EXISTS fk_parties_campaign;
    
    -- Drop and recreate campaigns table with UUID
    DROP TABLE IF EXISTS campaigns CASCADE;
    
    CREATE TABLE campaigns (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        description TEXT,
        story_weaver_id UUID,
        created_by_id UUID,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        join_code VARCHAR(6) UNIQUE,
        CONSTRAINT fk_campaigns_story_weaver FOREIGN KEY (story_weaver_id) REFERENCES users(id) ON DELETE SET NULL,
        CONSTRAINT fk_campaigns_created_by FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE SET NULL
    );
    
    -- Recreate FK from parties to campaigns
    ALTER TABLE parties ADD CONSTRAINT fk_parties_campaign 
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE;
    
    RAISE NOTICE '✅ Converted campaigns.id to UUID';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE '⚠️ Could not convert campaigns to UUID: %', SQLERRM;
END $$;