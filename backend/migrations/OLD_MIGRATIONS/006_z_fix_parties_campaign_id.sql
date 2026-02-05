-- ================================================================
-- TEMPORARY: Clear orphaned campaign_id references
-- This allows 007_create_campaigns.sql to create FK constraint
-- TODO: Remove this file after one successful deploy
-- ================================================================

DO $$
BEGIN
    -- Clear campaign_id from parties (prevents FK constraint error)
    UPDATE parties SET campaign_id = NULL WHERE campaign_id IS NOT NULL;
    
    -- Drop FK constraint if it exists
    ALTER TABLE parties DROP CONSTRAINT IF EXISTS fk_parties_campaign;
    
    RAISE NOTICE '✅ Cleared parties.campaign_id for UUID migration';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE '⚠️ Could not clear parties.campaign_id: %', SQLERRM;
END $$;