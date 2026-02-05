-- ================================================================
-- FORCE FIX: Convert campaigns.id to UUID (final attempt)
-- ================================================================

DO $$
BEGIN
    -- Drop everything that depends on campaigns
    DROP TABLE IF EXISTS campaign_memberships CASCADE;
    DROP VIEW IF EXISTS campaign_overview CASCADE;
    DROP TABLE IF EXISTS campaigns CASCADE;
    
    -- Recreate campaigns with UUID
    CREATE TABLE campaigns (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        description TEXT,
        story_weaver_id UUID,
        created_by_id UUID,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        join_code VARCHAR(6) UNIQUE,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        archived_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT fk_campaigns_story_weaver FOREIGN KEY (story_weaver_id) REFERENCES users(id) ON DELETE SET NULL,
        CONSTRAINT fk_campaigns_created_by FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE SET NULL
    );
    
    -- Recreate indexes
    CREATE INDEX IF NOT EXISTS idx_campaigns_story_weaver ON campaigns(story_weaver_id);
    CREATE INDEX IF NOT EXISTS idx_campaigns_created_by ON campaigns(created_by_id);
    CREATE INDEX IF NOT EXISTS idx_campaigns_active ON campaigns(is_active);
    
    -- Recreate FK from parties
    ALTER TABLE parties DROP CONSTRAINT IF EXISTS fk_parties_campaign;
    ALTER TABLE parties ADD CONSTRAINT fk_parties_campaign 
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE;
    
    RAISE NOTICE '✅ FORCE FIXED campaigns.id to UUID';
END $$;