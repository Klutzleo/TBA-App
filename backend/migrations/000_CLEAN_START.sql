-- ================================================================
-- CLEAN START: Create all tables with correct types from scratch
-- ================================================================
-- This runs FIRST and creates everything correctly
-- No more band-aids, no more fixes, just correct from the start
-- ================================================================

-- Drop everything (if exists)
DROP TABLE IF EXISTS password_reset_tokens CASCADE;
DROP TABLE IF EXISTS campaign_memberships CASCADE;
DROP TABLE IF EXISTS abilities CASCADE;
DROP TABLE IF EXISTS combat_turns CASCADE;
DROP TABLE IF EXISTS npcs CASCADE;
DROP TABLE IF EXISTS party_members CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS parties CASCADE;
DROP TABLE IF EXISTS characters CASCADE;
DROP TABLE IF EXISTS campaigns CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS echoes CASCADE;
DROP TABLE IF EXISTS roll_logs CASCADE;
DROP VIEW IF EXISTS campaign_overview CASCADE;
DROP TYPE IF EXISTS posting_frequency_enum CASCADE;
DROP TYPE IF EXISTS campaign_status_enum CASCADE;
DROP TYPE IF EXISTS campaign_role_enum CASCADE;

-- Create enums
CREATE TYPE posting_frequency_enum AS ENUM ('slow', 'medium', 'high');
CREATE TYPE campaign_status_enum AS ENUM ('active', 'archived', 'on_break');
CREATE TYPE campaign_role_enum AS ENUM ('player', 'story_weaver');

-- =====================================================================
-- 1. Create users table (UUID from start)
-- =====================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(50) NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);

-- =====================================================================
-- 2. Create campaigns table (UUID from start)
-- =====================================================================
CREATE TABLE campaigns (
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
CREATE INDEX idx_campaigns_story_weaver ON campaigns(story_weaver_id);
CREATE INDEX idx_campaigns_created_by ON campaigns(created_by_id);
CREATE INDEX idx_campaigns_active ON campaigns(is_active);
CREATE INDEX idx_campaigns_join_code ON campaigns(join_code);

-- =====================================================================
-- 3. Create characters table
-- =====================================================================
CREATE TABLE characters (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
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
CREATE INDEX idx_characters_name ON characters(name);
CREATE INDEX idx_characters_owner_id ON characters(owner_id);
CREATE INDEX idx_characters_user_id ON characters(user_id);
CREATE INDEX idx_characters_campaign_id ON characters(campaign_id);
CREATE INDEX idx_characters_status ON characters(status);

-- =====================================================================
-- 4. Create parties table (campaign_id is UUID from start!)
-- =====================================================================
CREATE TABLE parties (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    session_id VARCHAR(255),
    story_weaver_id VARCHAR(36),
    created_by_id VARCHAR(36) NOT NULL,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    party_type VARCHAR(20) NOT NULL DEFAULT 'standard',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_parties_campaign_id ON parties(campaign_id);
CREATE INDEX idx_parties_type ON parties(party_type);
CREATE INDEX idx_parties_active ON parties(is_active);

-- =====================================================================
-- 5. Create party_members table
-- =====================================================================
CREATE TABLE party_members (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    party_id VARCHAR(36) NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    character_id VARCHAR(36) NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at TIMESTAMPTZ NULL
);
CREATE INDEX idx_party_members_party_id ON party_members(party_id);
CREATE INDEX idx_party_members_character_id ON party_members(character_id);
CREATE UNIQUE INDEX idx_party_members_active_unique
    ON party_members(party_id, character_id)
    WHERE left_at IS NULL;

-- =====================================================================
-- 6. Create other tables
-- =====================================================================
CREATE TABLE abilities (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    character_id VARCHAR(36) NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    slot_number INTEGER NOT NULL,
    ability_type VARCHAR(50) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    macro_command VARCHAR(50) NOT NULL,
    power_source VARCHAR(10) NOT NULL,
    effect_type VARCHAR(50) NOT NULL,
    die VARCHAR(50) NOT NULL,
    is_aoe BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_abilities_character_id ON abilities(character_id);

CREATE TABLE npcs (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    party_id VARCHAR(36) NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
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
    created_by VARCHAR(36) NOT NULL,
    npc_type VARCHAR(20) NOT NULL DEFAULT 'neutral',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_npcs_party_id ON npcs(party_id);

CREATE TABLE messages (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    campaign_id UUID NOT NULL,
    party_id VARCHAR(36) REFERENCES parties(id) ON DELETE SET NULL,
    sender_id VARCHAR(36) NOT NULL,
    sender_name VARCHAR(255) NOT NULL,
    message_type VARCHAR(50) NOT NULL DEFAULT 'chat',
    mode VARCHAR(10),
    content TEXT NOT NULL,
    attachment_url VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_messages_campaign_id ON messages(campaign_id);
CREATE INDEX idx_messages_party_id ON messages(party_id);

CREATE TABLE combat_turns (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    party_id VARCHAR(36) NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    combatant_id VARCHAR(36) NOT NULL,
    combatant_name VARCHAR(255) NOT NULL,
    turn_number INTEGER NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    result_data JSON NOT NULL,
    bap_applied BOOLEAN NOT NULL DEFAULT FALSE,
    message_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_combat_turns_party_id ON combat_turns(party_id);

CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token VARCHAR NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);

CREATE TABLE campaign_memberships (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role campaign_role_enum NOT NULL DEFAULT 'player',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at TIMESTAMPTZ
);
CREATE INDEX idx_campaign_memberships_campaign_id ON campaign_memberships(campaign_id);
CREATE INDEX idx_campaign_memberships_user_id ON campaign_memberships(user_id);

-- =====================================================================
-- 7. Create view
-- =====================================================================
CREATE VIEW campaign_overview AS
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
