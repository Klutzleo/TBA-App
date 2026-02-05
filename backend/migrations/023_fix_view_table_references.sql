-- ================================================================
-- Migration 023: Fix View Table References
-- ================================================================
-- Problem: Multiple migrations created campaign_overview view with
-- references to "party_characters" table which doesn't exist.
-- The actual table name is "party_members" (created in 002).
--
-- Solution: Drop and recreate the view with correct table name.
-- ================================================================

DO $$
BEGIN
    -- Drop the view if it exists (it may have wrong table references)
    DROP VIEW IF EXISTS campaign_overview CASCADE;
    RAISE NOTICE '✅ Dropped campaign_overview view';

    -- Recreate campaign_overview view with CORRECT table reference
    -- Note: Using party_members (not party_characters or party_memberships)
    CREATE OR REPLACE VIEW campaign_overview AS
    SELECT
        c.id,
        c.name,
        c.description,
        c.story_weaver_id,
        c.created_by_id,
        c.is_active,
        c.created_at,
        c.join_code,
        c.is_public,
        c.status,
        u.username as story_weaver_username,
        u.email as story_weaver_email,
        COUNT(DISTINCT pm.character_id) as player_count,
        COUNT(DISTINCT CASE WHEN p.party_type = 'story' THEN p.id END) as story_channels,
        COUNT(DISTINCT CASE WHEN p.party_type = 'ooc' THEN p.id END) as ooc_channels,
        COUNT(DISTINCT CASE WHEN p.party_type = 'whisper' THEN p.id END) as whisper_channels,
        COUNT(DISTINCT CASE WHEN p.party_type = 'split_group' THEN p.id END) as split_group_channels
    FROM campaigns c
    LEFT JOIN users u ON c.story_weaver_id = u.id
    LEFT JOIN parties p ON p.campaign_id = c.id
    LEFT JOIN party_members pm ON pm.party_id = p.id AND pm.left_at IS NULL
    GROUP BY c.id, c.name, c.description, c.story_weaver_id, c.created_by_id,
             c.is_active, c.created_at, c.join_code, c.is_public, c.status,
             u.username, u.email;

    RAISE NOTICE '✅ Recreated campaign_overview view with correct table reference (party_members)';

    -- Add comment explaining the table name
    COMMENT ON VIEW campaign_overview IS 'Campaign overview with player counts from party_members table';

    RAISE NOTICE '✅✅✅ Migration 023: View table references fixed!';
    RAISE NOTICE 'Note: The correct table is party_members (not party_characters or party_memberships)';

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE '❌ Migration 023 failed: %', SQLERRM;
        RAISE;
END $$;
