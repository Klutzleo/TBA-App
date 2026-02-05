-- Migration 014: Fix Story Weaver to reference Users instead of Characters
-- This migration properly sets up campaigns to reference the Story Weaver's user account

-- Step 1: Drop the campaign_overview view (it depends on story_weaver_id column)
DROP VIEW IF EXISTS campaign_overview;

-- Step 2: Drop existing FK constraint if it exists
ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS fk_campaigns_story_weaver;
ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS campaigns_story_weaver_id_fkey;

-- Step 3: Clear story_weaver_id values (will need manual assignment later)
-- This is necessary because we're changing from character references to user references
UPDATE campaigns SET story_weaver_id = NULL;

-- Step 4: Change column type from VARCHAR to UUID
ALTER TABLE campaigns ALTER COLUMN story_weaver_id TYPE UUID USING story_weaver_id::uuid;

-- Step 5: Add new FK constraint to users table
ALTER TABLE campaigns
ADD CONSTRAINT fk_campaigns_story_weaver_user
FOREIGN KEY (story_weaver_id)
REFERENCES users(id)
ON DELETE SET NULL;

-- Step 6: Recreate the campaign_overview view with proper user reference
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

-- Step 7: Add comment explaining the architecture
COMMENT ON COLUMN campaigns.story_weaver_id IS 'References users.id - The user who runs this campaign as Story Weaver';
