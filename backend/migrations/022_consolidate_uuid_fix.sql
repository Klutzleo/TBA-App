-- ================================================================
-- Migration 022: Consolidated UUID Fix
-- ================================================================
-- This migration fixes the type mismatch issues between campaigns.id (UUID)
-- and all foreign key columns that reference it.
--
-- Problem: Multiple tables have campaign_id as VARCHAR(36) trying to reference
-- campaigns.id which is UUID. PostgreSQL doesn't allow FK between different types.
--
-- Solution: Convert all campaign_id columns to UUID in the correct order.
-- ================================================================

DO $$
DECLARE
    v_campaigns_exists BOOLEAN;
    v_campaigns_is_uuid BOOLEAN := FALSE;
BEGIN
    -- =====================================================================
    -- STEP 1: Drop the campaign_overview view (it blocks ALTER TABLE)
    -- =====================================================================
    DROP VIEW IF EXISTS campaign_overview CASCADE;
    RAISE NOTICE '✅ Dropped campaign_overview view';

    -- =====================================================================
    -- STEP 2: Check if campaigns table exists and what type id is
    -- =====================================================================
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'campaigns'
    ) INTO v_campaigns_exists;

    IF v_campaigns_exists THEN
        SELECT data_type = 'uuid' INTO v_campaigns_is_uuid
        FROM information_schema.columns
        WHERE table_name = 'campaigns' AND column_name = 'id';

        RAISE NOTICE 'Campaigns table exists, id is UUID: %', v_campaigns_is_uuid;
    END IF;

    -- =====================================================================
    -- STEP 3: Drop and recreate campaigns table with UUID if needed
    -- =====================================================================
    IF NOT v_campaigns_exists OR NOT v_campaigns_is_uuid THEN
        -- Drop all FK constraints that reference campaigns
        ALTER TABLE IF EXISTS parties DROP CONSTRAINT IF EXISTS fk_parties_campaign;
        ALTER TABLE IF EXISTS parties DROP CONSTRAINT IF EXISTS parties_campaign_id_fkey;
        ALTER TABLE IF EXISTS campaign_memberships DROP CONSTRAINT IF EXISTS fk_campaign_memberships_campaign;
        ALTER TABLE IF EXISTS characters DROP CONSTRAINT IF EXISTS fk_characters_campaign;

        -- Drop campaigns table
        DROP TABLE IF EXISTS campaigns CASCADE;

        -- Recreate campaigns with UUID
        CREATE TABLE campaigns (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            story_weaver_id UUID,
            created_by_id UUID,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            archived_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            -- Campaign management columns (from migration 013)
            join_code VARCHAR(6),
            is_public BOOLEAN NOT NULL DEFAULT TRUE,
            min_players INTEGER NOT NULL DEFAULT 2,
            max_players INTEGER NOT NULL DEFAULT 6,
            timezone VARCHAR NOT NULL DEFAULT 'America/New_York',
            posting_frequency posting_frequency_enum NOT NULL DEFAULT 'medium',
            status campaign_status_enum NOT NULL DEFAULT 'active',
            created_by_user_id UUID,
            CONSTRAINT fk_campaigns_story_weaver FOREIGN KEY (story_weaver_id)
                REFERENCES users(id) ON DELETE SET NULL,
            CONSTRAINT fk_campaigns_created_by FOREIGN KEY (created_by_id)
                REFERENCES users(id) ON DELETE SET NULL,
            CONSTRAINT fk_campaigns_created_by_user FOREIGN KEY (created_by_user_id)
                REFERENCES users(id) ON DELETE CASCADE
        );

        -- Create indexes
        CREATE INDEX idx_campaigns_story_weaver ON campaigns(story_weaver_id);
        CREATE INDEX idx_campaigns_created_by ON campaigns(created_by_id);
        CREATE INDEX idx_campaigns_active ON campaigns(is_active);
        CREATE INDEX idx_campaigns_join_code ON campaigns(join_code);
        CREATE INDEX idx_campaigns_created_by_user_id ON campaigns(created_by_user_id);

        -- Add unique constraint on join_code
        ALTER TABLE campaigns ADD CONSTRAINT campaigns_join_code_unique UNIQUE (join_code);

        RAISE NOTICE '✅ Recreated campaigns table with UUID id';
    END IF;

    -- =====================================================================
    -- STEP 4: Convert parties.campaign_id to UUID
    -- =====================================================================
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'parties' AND column_name = 'campaign_id'
    ) THEN
        -- Check current type
        DECLARE
            v_parties_campaign_type VARCHAR;
        BEGIN
            SELECT data_type INTO v_parties_campaign_type
            FROM information_schema.columns
            WHERE table_name = 'parties' AND column_name = 'campaign_id';

            IF v_parties_campaign_type != 'uuid' THEN
                -- Drop old constraint if exists
                ALTER TABLE parties DROP CONSTRAINT IF EXISTS fk_parties_campaign;
                ALTER TABLE parties DROP CONSTRAINT IF EXISTS parties_campaign_id_fkey;

                -- Clear invalid values
                UPDATE parties SET campaign_id = NULL
                WHERE campaign_id IS NOT NULL
                AND campaign_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

                -- Convert column type
                ALTER TABLE parties ALTER COLUMN campaign_id TYPE UUID
                    USING CASE
                        WHEN campaign_id IS NULL THEN NULL
                        WHEN campaign_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        THEN campaign_id::uuid
                        ELSE NULL
                    END;

                -- Add FK constraint
                ALTER TABLE parties ADD CONSTRAINT fk_parties_campaign
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE;

                RAISE NOTICE '✅ Converted parties.campaign_id to UUID';
            ELSE
                -- Ensure FK exists even if type is already correct
                ALTER TABLE parties DROP CONSTRAINT IF EXISTS fk_parties_campaign;
                ALTER TABLE parties DROP CONSTRAINT IF EXISTS parties_campaign_id_fkey;
                ALTER TABLE parties ADD CONSTRAINT fk_parties_campaign
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE;
                RAISE NOTICE 'parties.campaign_id already UUID, ensured FK exists';
            END IF;
        END;
    END IF;

    -- =====================================================================
    -- STEP 5: Convert campaign_memberships.campaign_id to UUID
    -- =====================================================================
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'campaign_memberships'
    ) THEN
        DECLARE
            v_cm_campaign_type VARCHAR;
        BEGIN
            SELECT data_type INTO v_cm_campaign_type
            FROM information_schema.columns
            WHERE table_name = 'campaign_memberships' AND column_name = 'campaign_id';

            IF v_cm_campaign_type != 'uuid' THEN
                -- Drop old constraint
                ALTER TABLE campaign_memberships DROP CONSTRAINT IF EXISTS fk_campaign_memberships_campaign;

                -- Clear invalid values
                UPDATE campaign_memberships SET campaign_id = NULL
                WHERE campaign_id IS NOT NULL
                AND campaign_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

                -- Convert column type
                ALTER TABLE campaign_memberships ALTER COLUMN campaign_id TYPE UUID
                    USING CASE
                        WHEN campaign_id IS NULL THEN NULL
                        WHEN campaign_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        THEN campaign_id::uuid
                        ELSE NULL
                    END;

                -- Add NOT NULL constraint
                ALTER TABLE campaign_memberships ALTER COLUMN campaign_id SET NOT NULL;

                -- Add FK constraint
                ALTER TABLE campaign_memberships ADD CONSTRAINT fk_campaign_memberships_campaign
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE;

                RAISE NOTICE '✅ Converted campaign_memberships.campaign_id to UUID';
            ELSE
                -- Ensure FK exists
                ALTER TABLE campaign_memberships DROP CONSTRAINT IF EXISTS fk_campaign_memberships_campaign;
                ALTER TABLE campaign_memberships ADD CONSTRAINT fk_campaign_memberships_campaign
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE;
                RAISE NOTICE 'campaign_memberships.campaign_id already UUID, ensured FK exists';
            END IF;
        END;
    END IF;

    -- =====================================================================
    -- STEP 6: Convert characters.campaign_id to UUID
    -- =====================================================================
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'characters' AND column_name = 'campaign_id'
    ) THEN
        DECLARE
            v_char_campaign_type VARCHAR;
        BEGIN
            SELECT data_type INTO v_char_campaign_type
            FROM information_schema.columns
            WHERE table_name = 'characters' AND column_name = 'campaign_id';

            IF v_char_campaign_type != 'uuid' THEN
                -- Drop old constraint
                ALTER TABLE characters DROP CONSTRAINT IF EXISTS fk_characters_campaign;

                -- Clear invalid values
                UPDATE characters SET campaign_id = NULL
                WHERE campaign_id IS NOT NULL
                AND campaign_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

                -- Convert column type
                ALTER TABLE characters ALTER COLUMN campaign_id TYPE UUID
                    USING CASE
                        WHEN campaign_id IS NULL THEN NULL
                        WHEN campaign_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        THEN campaign_id::uuid
                        ELSE NULL
                    END;

                -- Add FK constraint
                ALTER TABLE characters ADD CONSTRAINT fk_characters_campaign
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL;

                RAISE NOTICE '✅ Converted characters.campaign_id to UUID';
            ELSE
                -- Ensure FK exists
                ALTER TABLE characters DROP CONSTRAINT IF EXISTS fk_characters_campaign;
                ALTER TABLE characters ADD CONSTRAINT fk_characters_campaign
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL;
                RAISE NOTICE 'characters.campaign_id already UUID, ensured FK exists';
            END IF;
        END;
    END IF;

    -- =====================================================================
    -- STEP 7: Recreate campaign triggers
    -- =====================================================================

    -- Create function to auto-create Story and OOC channels for new campaigns
    CREATE OR REPLACE FUNCTION create_default_campaign_channels()
    RETURNS TRIGGER AS $func$
    BEGIN
        -- Create Story channel
        INSERT INTO parties (
            id,
            campaign_id,
            name,
            description,
            party_type,
            story_weaver_id,
            created_by_id,
            is_active
        ) VALUES (
            gen_random_uuid()::text,
            NEW.id,
            NEW.name || ' - Story',
            'Main story channel for ' || NEW.name,
            'story',
            NEW.story_weaver_id::text,
            NEW.created_by_id::text,
            TRUE
        );

        -- Create OOC channel
        INSERT INTO parties (
            id,
            campaign_id,
            name,
            description,
            party_type,
            story_weaver_id,
            created_by_id,
            is_active
        ) VALUES (
            gen_random_uuid()::text,
            NEW.id,
            NEW.name || ' - OOC',
            'Out-of-character chat for ' || NEW.name,
            'ooc',
            NEW.story_weaver_id::text,
            NEW.created_by_id::text,
            TRUE
        );

        RETURN NEW;
    END;
    $func$ LANGUAGE plpgsql;

    -- Create trigger to auto-create channels
    DROP TRIGGER IF EXISTS trigger_create_campaign_channels ON campaigns;
    CREATE TRIGGER trigger_create_campaign_channels
        AFTER INSERT ON campaigns
        FOR EACH ROW
        EXECUTE FUNCTION create_default_campaign_channels();

    -- Create updated_at trigger for campaigns
    CREATE OR REPLACE FUNCTION update_campaigns_updated_at()
    RETURNS TRIGGER AS $func$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $func$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trigger_campaigns_updated_at ON campaigns;
    CREATE TRIGGER trigger_campaigns_updated_at
        BEFORE UPDATE ON campaigns
        FOR EACH ROW
        EXECUTE FUNCTION update_campaigns_updated_at();

    RAISE NOTICE '✅ Recreated campaign triggers';

    -- =====================================================================
    -- STEP 8: Recreate campaign_overview view with correct schema
    -- =====================================================================
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
    LEFT JOIN party_memberships pm ON pm.party_id = p.id
    GROUP BY c.id, c.name, c.description, c.story_weaver_id, c.created_by_id,
             c.is_active, c.created_at, c.join_code, c.is_public, c.status,
             u.username, u.email;

    RAISE NOTICE '✅ Recreated campaign_overview view';

    -- =====================================================================
    -- Final success message
    -- =====================================================================
    RAISE NOTICE '✅✅✅ Migration 022: All UUID conversions completed successfully!';
    RAISE NOTICE 'campaigns.id: UUID';
    RAISE NOTICE 'parties.campaign_id: UUID with FK';
    RAISE NOTICE 'campaign_memberships.campaign_id: UUID with FK';
    RAISE NOTICE 'characters.campaign_id: UUID with FK';

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE '❌ Migration 022 failed: %', SQLERRM;
        RAISE;
END $$;
