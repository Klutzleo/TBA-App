-- ================================================================
-- NUCLEAR RESET: Drop everything and start clean
-- ================================================================
-- This drops ALL tables and starts from scratch
-- WARNING: This destroys all data!
-- ================================================================

DO $$
BEGIN
    RAISE NOTICE '💥 NUCLEAR RESET: Dropping all tables...';

    -- Drop all tables in correct order (FK constraints)
    DROP TABLE IF EXISTS password_reset_tokens CASCADE;
    DROP TABLE IF EXISTS campaign_memberships CASCADE;
    DROP TABLE IF EXISTS abilities CASCADE;
    DROP TABLE IF EXISTS combat_turns CASCADE;
    DROP TABLE IF EXISTS npcs CASCADE;
    DROP TABLE IF EXISTS party_members CASCADE;
    DROP TABLE IF EXISTS party_memberships CASCADE;
    DROP TABLE IF EXISTS messages CASCADE;
    DROP TABLE IF EXISTS parties CASCADE;
    DROP TABLE IF EXISTS characters CASCADE;
    DROP TABLE IF EXISTS campaigns CASCADE;
    DROP TABLE IF EXISTS users CASCADE;
    DROP TABLE IF EXISTS echoes CASCADE;
    DROP TABLE IF EXISTS roll_logs CASCADE;

    -- Drop all views
    DROP VIEW IF EXISTS campaign_overview CASCADE;

    -- Drop all triggers
    DROP TRIGGER IF EXISTS trigger_create_campaign_channels ON campaigns;
    DROP TRIGGER IF EXISTS trigger_campaigns_updated_at ON campaigns;
    DROP TRIGGER IF EXISTS trigger_parties_updated_at ON parties;

    -- Drop all functions
    DROP FUNCTION IF EXISTS create_default_campaign_channels() CASCADE;
    DROP FUNCTION IF EXISTS update_campaigns_updated_at() CASCADE;
    DROP FUNCTION IF EXISTS update_parties_updated_at() CASCADE;

    -- Drop all enums
    DROP TYPE IF EXISTS posting_frequency_enum CASCADE;
    DROP TYPE IF EXISTS campaign_status_enum CASCADE;
    DROP TYPE IF EXISTS campaign_role_enum CASCADE;

    RAISE NOTICE '✅ All tables, views, triggers, and functions dropped';
    RAISE NOTICE '💥 Database is now empty - ready for clean migration';

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE '❌ Nuclear reset failed: %', SQLERRM;
        RAISE;
END $$;
