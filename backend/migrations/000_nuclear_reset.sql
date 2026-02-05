-- Nuclear Reset: Drop EVERYTHING
-- Use with extreme caution - destroys all data

DO $$
BEGIN
    RAISE NOTICE '💥 Starting nuclear reset...';

    -- Drop all views first
    DROP VIEW IF EXISTS campaign_overview CASCADE;
    RAISE NOTICE 'Dropped views';

    -- Drop all tables (in reverse dependency order)
    DROP TABLE IF EXISTS combat_turns CASCADE;
    DROP TABLE IF EXISTS roll_logs CASCADE;
    DROP TABLE IF EXISTS echoes CASCADE;
    DROP TABLE IF EXISTS messages CASCADE;
    DROP TABLE IF EXISTS abilities CASCADE;
    DROP TABLE IF EXISTS npcs CASCADE;
    DROP TABLE IF EXISTS party_memberships CASCADE;
    DROP TABLE IF EXISTS party_members CASCADE;
    DROP TABLE IF EXISTS campaign_memberships CASCADE;
    DROP TABLE IF EXISTS password_reset_tokens CASCADE;
    DROP TABLE IF EXISTS parties CASCADE;
    DROP TABLE IF EXISTS characters CASCADE;
    DROP TABLE IF EXISTS campaigns CASCADE;
    DROP TABLE IF EXISTS users CASCADE;
    RAISE NOTICE 'Dropped all tables';

    -- Drop all custom types
    DROP TYPE IF EXISTS campaign_role_enum CASCADE;
    DROP TYPE IF EXISTS message_type CASCADE;
    DROP TYPE IF EXISTS combat_phase CASCADE;
    RAISE NOTICE 'Dropped custom types';

    -- Drop all functions/triggers
    DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
    DROP FUNCTION IF EXISTS assign_story_weaver() CASCADE;
    RAISE NOTICE 'Dropped functions';

    RAISE NOTICE '✅ Nuclear reset complete - database is clean!';
    RAISE NOTICE '🔄 Now run migrations to rebuild schema';
END $$;