-- Migration 013: Add Campaign Management System
-- Phase 3 Part 2: Campaign browsing, join codes, and user-based ownership

-- ==================== ENUMS ====================

-- Create posting frequency enum
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'posting_frequency_enum') THEN
        CREATE TYPE posting_frequency_enum AS ENUM ('slow', 'medium', 'high');
        RAISE NOTICE 'Created posting_frequency_enum';
    ELSE
        RAISE NOTICE 'posting_frequency_enum already exists';
    END IF;
END $$;

-- Create campaign status enum
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'campaign_status_enum') THEN
        CREATE TYPE campaign_status_enum AS ENUM ('active', 'archived', 'on_break');
        RAISE NOTICE 'Created campaign_status_enum';
    ELSE
        RAISE NOTICE 'campaign_status_enum already exists';
    END IF;
END $$;

-- Create campaign role enum
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'campaign_role_enum') THEN
        CREATE TYPE campaign_role_enum AS ENUM ('player', 'story_weaver');
        RAISE NOTICE 'Created campaign_role_enum';
    ELSE
        RAISE NOTICE 'campaign_role_enum already exists';
    END IF;
END $$;


-- ==================== UPDATE CAMPAIGNS TABLE ====================

-- Add join_code column with unique constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'campaigns' AND column_name = 'join_code'
    ) THEN
        -- Add column
        ALTER TABLE campaigns ADD COLUMN join_code VARCHAR(6);

        -- Generate unique join codes for existing campaigns
        UPDATE campaigns SET join_code = UPPER(SUBSTRING(MD5(id::text) FROM 1 FOR 6))
        WHERE join_code IS NULL;

        -- Make it NOT NULL and unique
        ALTER TABLE campaigns ALTER COLUMN join_code SET NOT NULL;
        ALTER TABLE campaigns ADD CONSTRAINT campaigns_join_code_unique UNIQUE (join_code);

        -- Add index for fast lookups
        CREATE INDEX idx_campaigns_join_code ON campaigns(join_code);

        RAISE NOTICE 'Added join_code column with unique constraint';
    ELSE
        RAISE NOTICE 'join_code column already exists';
    END IF;
END $$;

-- Add is_public column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'campaigns' AND column_name = 'is_public'
    ) THEN
        ALTER TABLE campaigns ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT TRUE;
        RAISE NOTICE 'Added is_public column';
    ELSE
        RAISE NOTICE 'is_public column already exists';
    END IF;
END $$;

-- Add min_players column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'campaigns' AND column_name = 'min_players'
    ) THEN
        ALTER TABLE campaigns ADD COLUMN min_players INTEGER NOT NULL DEFAULT 2;
        RAISE NOTICE 'Added min_players column';
    ELSE
        RAISE NOTICE 'min_players column already exists';
    END IF;
END $$;

-- Add max_players column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'campaigns' AND column_name = 'max_players'
    ) THEN
        ALTER TABLE campaigns ADD COLUMN max_players INTEGER NOT NULL DEFAULT 6;
        RAISE NOTICE 'Added max_players column';
    ELSE
        RAISE NOTICE 'max_players column already exists';
    END IF;
END $$;

-- Add timezone column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'campaigns' AND column_name = 'timezone'
    ) THEN
        ALTER TABLE campaigns ADD COLUMN timezone VARCHAR NOT NULL DEFAULT 'America/New_York';
        RAISE NOTICE 'Added timezone column';
    ELSE
        RAISE NOTICE 'timezone column already exists';
    END IF;
END $$;

-- Add posting_frequency column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'campaigns' AND column_name = 'posting_frequency'
    ) THEN
        ALTER TABLE campaigns ADD COLUMN posting_frequency posting_frequency_enum NOT NULL DEFAULT 'medium';
        RAISE NOTICE 'Added posting_frequency column';
    ELSE
        RAISE NOTICE 'posting_frequency column already exists';
    END IF;
END $$;

-- Add status column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'campaigns' AND column_name = 'status'
    ) THEN
        ALTER TABLE campaigns ADD COLUMN status campaign_status_enum NOT NULL DEFAULT 'active';
        RAISE NOTICE 'Added status column';
    ELSE
        RAISE NOTICE 'status column already exists';
    END IF;
END $$;

-- Add created_by_user_id column (new user-based ownership)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'campaigns' AND column_name = 'created_by_user_id'
    ) THEN
        -- Add column as nullable first
        ALTER TABLE campaigns ADD COLUMN created_by_user_id VARCHAR;

        -- Add foreign key constraint
        ALTER TABLE campaigns ADD CONSTRAINT fk_campaigns_created_by_user
            FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE CASCADE;

        -- Add index
        CREATE INDEX idx_campaigns_created_by_user_id ON campaigns(created_by_user_id);

        RAISE NOTICE 'Added created_by_user_id column with FK to users';
    ELSE
        RAISE NOTICE 'created_by_user_id column already exists';
    END IF;
END $$;

-- Update story_weaver_id to reference users instead of characters
DO $$
BEGIN
    -- Check if story_weaver_id currently references characters
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage ccu USING (constraint_name)
        WHERE tc.table_name = 'campaigns'
        AND tc.constraint_type = 'FOREIGN KEY'
        AND ccu.table_name = 'characters'
        AND ccu.column_name = 'id'
        AND tc.constraint_name LIKE '%story_weaver%'
    ) THEN
        -- Drop old FK to characters
        ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS fk_campaigns_story_weaver;
        ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS campaigns_story_weaver_id_fkey;

        -- Clear story_weaver_id (will need manual migration to map characters to users)
        UPDATE campaigns SET story_weaver_id = NULL;

        -- Add new FK to users
        ALTER TABLE campaigns ADD CONSTRAINT fk_campaigns_story_weaver_user
            FOREIGN KEY (story_weaver_id) REFERENCES users(id) ON DELETE SET NULL;

        RAISE NOTICE 'Updated story_weaver_id to reference users table';
    ELSE
        RAISE NOTICE 'story_weaver_id already references users or no constraint exists';
    END IF;
END $$;

-- Make description TEXT instead of VARCHAR
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'campaigns'
        AND column_name = 'description'
        AND data_type != 'text'
    ) THEN
        ALTER TABLE campaigns ALTER COLUMN description TYPE TEXT;
        RAISE NOTICE 'Changed description to TEXT type';
    ELSE
        RAISE NOTICE 'description is already TEXT or does not exist';
    END IF;
END $$;


-- ==================== CREATE CAMPAIGN_MEMBERSHIPS TABLE ====================

CREATE TABLE IF NOT EXISTS campaign_memberships (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    campaign_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    role campaign_role_enum NOT NULL DEFAULT 'player',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at TIMESTAMPTZ,

    CONSTRAINT fk_campaign_memberships_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    CONSTRAINT fk_campaign_memberships_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_campaign_memberships_campaign_id ON campaign_memberships(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_memberships_user_id ON campaign_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_campaign_memberships_left_at ON campaign_memberships(left_at);

-- Add comments for documentation
COMMENT ON TABLE campaign_memberships IS 'Tracks user membership in campaigns with roles and history';
COMMENT ON COLUMN campaign_memberships.role IS 'User role in campaign: player or story_weaver';
COMMENT ON COLUMN campaign_memberships.left_at IS 'NULL means user is still active member';

COMMENT ON COLUMN campaigns.join_code IS '6-character code for joining campaign (e.g., A3K9M2)';
COMMENT ON COLUMN campaigns.is_public IS 'Whether campaign appears in public browse list';
COMMENT ON COLUMN campaigns.posting_frequency IS 'Expected posting pace: slow, medium, high';
COMMENT ON COLUMN campaigns.status IS 'Campaign state: active, archived, on_break';

SELECT 'Migration 013: Campaign management system with join codes and user ownership' AS status;
