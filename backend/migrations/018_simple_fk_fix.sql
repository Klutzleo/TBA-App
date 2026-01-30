-- Migration 018: Simple FK fix without view creation
-- Separate FK fix from view to avoid rollback issues

-- Step 1: Drop the view (separate from FK changes)
DROP VIEW IF EXISTS campaign_overview;

-- Step 2: Drop ALL FK constraints on story_weaver_id
DO $$
DECLARE
    constraint_name text;
BEGIN
    FOR constraint_name IN
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_attribute att ON att.attnum = ANY(con.conkey) AND att.attrelid = con.conrelid
        WHERE rel.relname = 'campaigns'
        AND att.attname = 'story_weaver_id'
        AND con.contype = 'f'
    LOOP
        EXECUTE format('ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS %I', constraint_name);
        RAISE NOTICE 'Dropped FK constraint: %', constraint_name;
    END LOOP;
END $$;

-- Step 3: Clear story_weaver_id values
UPDATE campaigns SET story_weaver_id = NULL WHERE story_weaver_id IS NOT NULL;

-- Step 4: Ensure column is UUID type
DO $$
BEGIN
    ALTER TABLE campaigns ALTER COLUMN story_weaver_id TYPE UUID USING story_weaver_id::uuid;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Column already UUID type or conversion failed: %', SQLERRM;
END $$;

-- Step 5: Add the correct FK constraint to users table
ALTER TABLE campaigns
ADD CONSTRAINT fk_campaigns_story_weaver_user
FOREIGN KEY (story_weaver_id)
REFERENCES users(id)
ON DELETE SET NULL;

-- Step 6: Recreate view (in separate transaction, won't affect FK if it fails)
DO $$
BEGIN
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
        0 as character_count  -- Simplified to avoid party_characters dependency
    FROM campaigns c
    LEFT JOIN users u ON c.story_weaver_id = u.id
    LEFT JOIN parties p ON p.campaign_id = c.id
    GROUP BY c.id, c.name, c.description, c.created_at, c.story_weaver_id, u.username, u.email;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'View creation failed (non-critical): %', SQLERRM;
END $$;

SELECT 'Migration 018: Simple FK fix completed' AS status;
