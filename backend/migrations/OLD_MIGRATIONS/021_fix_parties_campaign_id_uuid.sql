-- Fix parties.campaign_id to match campaigns.id (UUID)
DO $$
BEGIN
    -- Clear any existing values
    UPDATE parties SET campaign_id = NULL WHERE campaign_id IS NOT NULL;
    
    -- Drop old constraint if exists
    ALTER TABLE parties DROP CONSTRAINT IF EXISTS fk_parties_campaign;
    
    -- Convert column to UUID
    ALTER TABLE parties ALTER COLUMN campaign_id TYPE UUID USING campaign_id::uuid;
    
    -- Recreate FK
    ALTER TABLE parties ADD CONSTRAINT fk_parties_campaign 
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE;
    
    RAISE NOTICE '✅ parties.campaign_id converted to UUID';
END $$;