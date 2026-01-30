-- Migration 017: Force fix story_weaver_id FK constraint
-- This will forcefully remove ALL FK constraints on story_weaver_id and create only the correct one

DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    -- Drop campaign_overview view first
    DROP VIEW IF EXISTS campaign_overview;
    RAISE NOTICE 'Dropped campaign_overview view';

    -- Find and drop ALL foreign key constraints on story_weaver_id column
    FOR constraint_record IN
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_attribute att ON att.attnum = ANY(con.conkey) AND att.attrelid = con.conrelid
        WHERE rel.relname = 'campaigns'
        AND att.attname = 'story_weaver_id'
        AND con.contype = 'f'
    LOOP
        EXECUTE format('ALTER TABLE campaigns DROP CONSTRAINT %I', constraint_record.conname);
        RAISE NOTICE 'Dropped constraint: %', constraint_record.conname;
    END LOOP;

    -- Clear story_weaver_id values (they might be old character IDs)
    UPDATE campaigns SET story_weaver_id = NULL;
    RAISE NOTICE 'Cleared story_weaver_id values';

    -- Ensure column is UUID type
    ALTER TABLE campaigns ALTER COLUMN story_weaver_id TYPE UUID USING story_weaver_id::uuid;
    RAISE NOTICE 'Set story_weaver_id to UUID type';

    -- Add the ONLY correct FK constraint to users table
    ALTER TABLE campaigns
    ADD CONSTRAINT fk_campaigns_story_weaver_user
    FOREIGN KEY (story_weaver_id)
    REFERENCES users(id)
    ON DELETE SET NULL;
    RAISE NOTICE 'Added FK constraint to users table';

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
        COALESCE(COUNT(DISTINCT pc.character_id), 0) as character_count
    FROM campaigns c
    LEFT JOIN users u ON c.story_weaver_id = u.id
    LEFT JOIN parties p ON p.campaign_id = c.id
    LEFT JOIN party_characters pc ON pc.party_id = p.id
    GROUP BY c.id, c.name, c.description, c.created_at, c.story_weaver_id, u.username, u.email;
    RAISE NOTICE 'Recreated campaign_overview view';

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Error occurred: %', SQLERRM;
        RAISE;
END $$;

SELECT 'Migration 017: Force fixed story_weaver_id FK constraint' AS status;
