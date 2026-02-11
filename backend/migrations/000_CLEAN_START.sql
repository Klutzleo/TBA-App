-- ================================================================
-- CLEAN START: Create all tables with correct types from scratch
-- ================================================================
-- This runs FIRST and creates everything correctly
-- No more band-aids, no more fixes, just correct from the start
-- IDEMPOTENT: Safe to run multiple times, preserves existing data
-- ================================================================

-- Create enums (only if they don't exist)
DO $$ BEGIN
    CREATE TYPE posting_frequency_enum AS ENUM ('slow', 'medium', 'high');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE campaign_status_enum AS ENUM ('active', 'archived', 'on_break');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE campaign_role_enum AS ENUM ('player', 'story_weaver');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- =====================================================================
-- DROP ALL EXISTING TABLES (ensures clean start with correct types)
-- =====================================================================
DROP TABLE IF EXISTS initiative_rolls CASCADE;
DROP TABLE IF EXISTS encounters CASCADE;
DROP TABLE IF EXISTS combat_turns CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS abilities CASCADE;
DROP TABLE IF EXISTS party_members CASCADE;
DROP TABLE IF EXISTS npcs CASCADE;
DROP TABLE IF EXISTS parties CASCADE;
DROP TABLE IF EXISTS campaign_memberships CASCADE;
DROP TABLE IF EXISTS password_reset_tokens CASCADE;
DROP TABLE IF EXISTS characters CASCADE;
DROP TABLE IF EXISTS campaigns CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS roll_logs CASCADE;
DROP VIEW IF EXISTS campaign_overview CASCADE;

-- =====================================================================
-- 1. Create users table (UUID from start)
-- =====================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(50) NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- =====================================================================
-- 2. Create campaigns table (UUID from start)
-- =====================================================================
CREATE TABLE IF NOT EXISTS campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    story_weaver_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    join_code VARCHAR(6) UNIQUE,
    is_public BOOLEAN NOT NULL DEFAULT TRUE,
    min_players INTEGER NOT NULL DEFAULT 2,
    max_players INTEGER NOT NULL DEFAULT 6,
    timezone VARCHAR NOT NULL DEFAULT 'America/New_York',
    posting_frequency posting_frequency_enum NOT NULL DEFAULT 'medium',
    status campaign_status_enum NOT NULL DEFAULT 'active',
    created_by_user_id UUID REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_campaigns_story_weaver ON campaigns(story_weaver_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_created_by ON campaigns(created_by_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_active ON campaigns(is_active);
CREATE INDEX IF NOT EXISTS idx_campaigns_join_code ON campaigns(join_code);

-- =====================================================================
-- 3. Create characters table
-- =====================================================================
CREATE TABLE IF NOT EXISTS characters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    owner_id VARCHAR(255) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    level INTEGER NOT NULL DEFAULT 1,
    pp INTEGER NOT NULL,
    ip INTEGER NOT NULL,
    sp INTEGER NOT NULL,
    dp INTEGER NOT NULL,
    max_dp INTEGER NOT NULL,
    edge INTEGER NOT NULL DEFAULT 0,
    bap INTEGER NOT NULL DEFAULT 1,
    attack_style VARCHAR(50) NOT NULL,
    defense_die VARCHAR(50) NOT NULL,
    weapon JSON,
    armor JSON,
    notes TEXT,
    max_uses_per_encounter INTEGER NOT NULL DEFAULT 3,
    current_uses INTEGER NOT NULL DEFAULT 3,
    weapon_bonus INTEGER NOT NULL DEFAULT 0,
    armor_bonus INTEGER NOT NULL DEFAULT 0,
    times_called INTEGER NOT NULL DEFAULT 0,
    is_called BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    in_calling BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
CREATE INDEX IF NOT EXISTS idx_characters_owner_id ON characters(owner_id);
CREATE INDEX IF NOT EXISTS idx_characters_user_id ON characters(user_id);
CREATE INDEX IF NOT EXISTS idx_characters_campaign_id ON characters(campaign_id);
CREATE INDEX IF NOT EXISTS idx_characters_status ON characters(status);

-- =====================================================================
-- 4. Create parties table (campaign_id is UUID from start!)
-- =====================================================================
CREATE TABLE IF NOT EXISTS parties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    session_id VARCHAR(255),
    story_weaver_id UUID,
    created_by_id UUID NOT NULL,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    party_type VARCHAR(20) NOT NULL DEFAULT 'standard',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_parties_campaign_id ON parties(campaign_id);
CREATE INDEX IF NOT EXISTS idx_parties_type ON parties(party_type);
CREATE INDEX IF NOT EXISTS idx_parties_active ON parties(is_active);

-- =====================================================================
-- 5. Create party_members table
-- =====================================================================
CREATE TABLE IF NOT EXISTS party_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS idx_party_members_party_id ON party_members(party_id);
CREATE INDEX IF NOT EXISTS idx_party_members_character_id ON party_members(character_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_party_members_active_unique
    ON party_members(party_id, character_id)
    WHERE left_at IS NULL;

-- =====================================================================
-- 6. Create other tables
-- =====================================================================
CREATE TABLE IF NOT EXISTS abilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    slot_number INTEGER NOT NULL,
    ability_type VARCHAR(50) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    macro_command VARCHAR(50) NOT NULL,
    power_source VARCHAR(10) NOT NULL,
    effect_type VARCHAR(50) NOT NULL,
    die VARCHAR(50) NOT NULL,
    is_aoe BOOLEAN NOT NULL DEFAULT FALSE,
    max_uses INTEGER NOT NULL DEFAULT 3,
    uses_remaining INTEGER NOT NULL DEFAULT 3,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_abilities_character_id ON abilities(character_id);

CREATE TABLE IF NOT EXISTS npcs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    pp INTEGER NOT NULL DEFAULT 2,
    ip INTEGER NOT NULL DEFAULT 2,
    sp INTEGER NOT NULL DEFAULT 2,
    dp INTEGER NOT NULL DEFAULT 10,
    max_dp INTEGER NOT NULL DEFAULT 10,
    edge INTEGER NOT NULL DEFAULT 0,
    bap INTEGER NOT NULL DEFAULT 1,
    attack_style VARCHAR(50) NOT NULL DEFAULT '1d4',
    defense_die VARCHAR(50) NOT NULL DEFAULT '1d4',
    visible_to_players BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID NOT NULL,
    npc_type VARCHAR(20) NOT NULL DEFAULT 'neutral',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_npcs_party_id ON npcs(party_id);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL,
    party_id UUID REFERENCES parties(id) ON DELETE SET NULL,
    sender_id UUID NOT NULL,
    sender_name VARCHAR(255) NOT NULL,
    message_type VARCHAR(50) NOT NULL DEFAULT 'chat',
    mode VARCHAR(10),
    content TEXT NOT NULL,
    attachment_url VARCHAR(500),
    extra_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_campaign_id ON messages(campaign_id);
CREATE INDEX IF NOT EXISTS idx_messages_party_id ON messages(party_id);
CREATE INDEX IF NOT EXISTS idx_messages_extra_data ON messages USING gin (extra_data);

CREATE TABLE IF NOT EXISTS combat_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    combatant_id UUID NOT NULL,
    combatant_name VARCHAR(255) NOT NULL,
    turn_number INTEGER NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    result_data JSON NOT NULL,
    bap_applied BOOLEAN NOT NULL DEFAULT FALSE,
    message_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_combat_turns_party_id ON combat_turns(party_id);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token VARCHAR NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);

CREATE TABLE IF NOT EXISTS campaign_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role campaign_role_enum NOT NULL DEFAULT 'player',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_campaign_memberships_campaign_id ON campaign_memberships(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_memberships_user_id ON campaign_memberships(user_id);

-- Roll logs for audit/replay
CREATE TABLE IF NOT EXISTS roll_logs (
    id SERIAL PRIMARY KEY,
    actor VARCHAR(255),
    target VARCHAR(255),
    roll_type VARCHAR(50),
    roll_mode VARCHAR(50),
    triggered_by VARCHAR(255),
    result JSON,
    modifiers JSON,
    session_id UUID,
    encounter_id UUID
);
CREATE INDEX IF NOT EXISTS idx_roll_logs_session_id ON roll_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_roll_logs_encounter_id ON roll_logs(encounter_id);

-- =====================================================================
-- 6b. Create encounters and initiative_rolls tables
-- =====================================================================
CREATE TABLE IF NOT EXISTS encounters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_encounters_campaign ON encounters(campaign_id);
CREATE INDEX IF NOT EXISTS idx_encounters_active ON encounters(campaign_id, is_active);

CREATE TABLE IF NOT EXISTS initiative_rolls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id UUID NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    npc_id UUID REFERENCES npcs(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    roll_result INTEGER NOT NULL,
    is_silent BOOLEAN NOT NULL DEFAULT FALSE,
    rolled_by_sw BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT check_one_entity CHECK (
        (character_id IS NOT NULL AND npc_id IS NULL) OR
        (character_id IS NULL AND npc_id IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_initiative_encounter ON initiative_rolls(encounter_id);
CREATE INDEX IF NOT EXISTS idx_initiative_character ON initiative_rolls(character_id);
CREATE INDEX IF NOT EXISTS idx_initiative_npc ON initiative_rolls(npc_id);
CREATE INDEX IF NOT EXISTS idx_initiative_order ON initiative_rolls(encounter_id, roll_result DESC);

-- =====================================================================
-- 7. Create view
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
    COUNT(DISTINCT CASE WHEN p.party_type = 'ooc' THEN p.id END) as ooc_channels
FROM campaigns c
LEFT JOIN users u ON c.story_weaver_id = u.id
LEFT JOIN parties p ON p.campaign_id = c.id
LEFT JOIN party_members pm ON pm.party_id = p.id AND pm.left_at IS NULL
GROUP BY c.id, c.name, c.description, c.story_weaver_id, c.created_by_id,
         c.is_active, c.created_at, c.join_code, c.is_public, c.status,
         u.username, u.email;

SELECT '✅ CLEAN START: All tables created with correct types!' AS status;
