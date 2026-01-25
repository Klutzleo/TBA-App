-- Make story_weaver_id nullable in parties table
-- This is correct for the architecture: SW is a campaign-level role, not channel-level
ALTER TABLE parties ALTER COLUMN story_weaver_id DROP NOT NULL;

-- Also make campaign fields nullable for bootstrapping
ALTER TABLE campaigns ALTER COLUMN story_weaver_id DROP NOT NULL;
ALTER TABLE campaigns ALTER COLUMN created_by_id DROP NOT NULL;

-- Make character.campaign_id nullable temporarily for bootstrapping
ALTER TABLE characters ALTER COLUMN campaign_id DROP NOT NULL;

SELECT 'Migration 008 completed: Made story_weaver_id and campaign fields nullable for bootstrapping' AS status;
