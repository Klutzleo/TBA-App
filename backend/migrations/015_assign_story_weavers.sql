-- Migration 015: Assign Story Weavers to existing campaigns
-- This assigns the system user as Story Weaver for campaigns that don't have one yet

-- Find the system user ID
DO $$
DECLARE
    system_user_id UUID;
BEGIN
    -- Get the system user (or any user as fallback)
    SELECT id INTO system_user_id
    FROM users
    WHERE email = 'system@tba-app.local'
    LIMIT 1;

    -- If no system user exists, use the first user
    IF system_user_id IS NULL THEN
        SELECT id INTO system_user_id FROM users LIMIT 1;
    END IF;

    -- Assign system user to campaigns without a story weaver
    IF system_user_id IS NOT NULL THEN
        UPDATE campaigns
        SET story_weaver_id = system_user_id
        WHERE story_weaver_id IS NULL;

        RAISE NOTICE 'Assigned Story Weaver (user %) to campaigns without one', system_user_id;
    ELSE
        RAISE NOTICE 'No users found - campaigns will remain without Story Weaver';
    END IF;
END $$;

-- Show campaign assignments
SELECT
    c.id,
    c.name,
    c.story_weaver_id,
    u.username as story_weaver,
    u.email
FROM campaigns c
LEFT JOIN users u ON c.story_weaver_id = u.id
ORDER BY c.created_at;
