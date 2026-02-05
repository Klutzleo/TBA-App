-- Migration 016: Fix story_weaver_id foreign key constraint
-- Ensures the FK points to users table, not characters table

DO $$
BEGIN
    -- Drop campaign_overview view first (it depends on the column)
    DROP VIEW IF EXISTS campaign_overview;
    RAISE NOTICE 'Dropped campaign_overview view';

    -- Drop ALL possible old FK constraints
    ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS fk_campaigns_story_weaver;
    ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS campaigns_story_weaver_id_fkey;
    ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS fk_story_weaver;

    RAISE NOTICE 'Dropped old FK constraints';

    -- Clear story_weaver_id values (they're character IDs, not user IDs)
    UPDATE campaigns SET story_weaver_id = NULL;
    RAISE NOTICE 'Cleared story_weaver_id values';

    -- Ensure column is UUID type
    ALTER TABLE campaigns ALTER COLUMN story_weaver_id TYPE UUID USING story_weaver_id::uuid;
    RAISE NOTICE 'Changed story_weaver_id to UUID type';

    -- Add new FK constraint to users table
    ALTER TABLE campaigns
    ADD CONSTRAINT fk_campaigns_story_weaver_user
    FOREIGN KEY (story_weaver_id)
    REFERENCES users(id)
    ON DELETE SET NULL;

    RAISE NOTICE 'Added new FK constraint to users table';

    -- Recreate campaign_overview view
    CREATE OR REPLACE VIEW campaign_overview AS
    SELECT
        c.id,
        c.name,
        c.description,
        c.created_at,
        c.story_weaver_id,
        u.username as story_weaver_username,
        u.email as story_weaver_email,
        COUNT(DISTINCT p.id) as party_count,
        COUNT(DISTINCT pc.character_id) as character_count
    FROM campaigns c
    LEFT JOIN users u ON c.story_weaver_id = u.id
    LEFT JOIN parties p ON p.campaign_id = c.id
    LEFT JOIN party_characters pc ON pc.party_id = p.id
    GROUP BY c.id, c.name, c.description, c.created_at, c.story_weaver_id, u.username, u.email;

    RAISE NOTICE 'Recreated campaign_overview view';
END $$;

SELECT 'Migration 016: Fixed story_weaver_id FK to point to users table' AS status;
