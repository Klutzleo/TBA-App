-- Migration 000: Create Base Schema
-- Creates all core tables if they don't exist
-- Safe to run multiple times (uses IF NOT EXISTS)

-- =====================================================================
-- 1. Create characters table
-- =====================================================================
CREATE TABLE IF NOT EXISTS characters (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    owner_id VARCHAR(255) NOT NULL,
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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,
    max_uses_per_encounter INTEGER NOT NULL DEFAULT 3,
    current_uses INTEGER NOT NULL DEFAULT 3,
    weapon_bonus INTEGER NOT NULL DEFAULT 0,
    armor_bonus INTEGER NOT NULL DEFAULT 0,
    times_called INTEGER NOT NULL DEFAULT 0,
    is_called BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    in_calling BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
CREATE INDEX IF NOT EXISTS idx_characters_owner_id ON characters(owner_id);
CREATE INDEX IF NOT EXISTS idx_characters_status ON characters(status);

-- =====================================================================
-- 2. Create parties table
-- =====================================================================
CREATE TABLE IF NOT EXISTS parties (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    session_id VARCHAR(255),
    story_weaver_id VARCHAR(36),
    created_by_id VARCHAR(36) NOT NULL,
    campaign_id VARCHAR(36),
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
-- 3. Create party_memberships table
-- =====================================================================
CREATE TABLE IF NOT EXISTS party_memberships (
    id VARCHAR(36) PRIMARY KEY,
    party_id VARCHAR(36) NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    character_id VARCHAR(36) NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    left_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_party_memberships_party_id ON party_memberships(party_id);
CREATE INDEX IF NOT EXISTS idx_party_memberships_character_id ON party_memberships(character_id);

-- =====================================================================
-- 4. Create npcs table
-- =====================================================================
CREATE TABLE IF NOT EXISTS npcs (
    id VARCHAR(36) PRIMARY KEY,
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

CREATE INDEX IF NOT EXISTS idx_npcs_party_id ON npcs(party_id);
CREATE INDEX IF NOT EXISTS idx_npcs_name ON npcs(name);

-- =====================================================================
-- 5. Create combat_turns table
-- =====================================================================
CREATE TABLE IF NOT EXISTS combat_turns (
    id VARCHAR(36) PRIMARY KEY,
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

CREATE INDEX IF NOT EXISTS idx_combat_turns_party_id ON combat_turns(party_id);
CREATE INDEX IF NOT EXISTS idx_combat_turns_turn_number ON combat_turns(turn_number);
CREATE INDEX IF NOT EXISTS idx_combat_turns_message_id ON combat_turns(message_id);
CREATE INDEX IF NOT EXISTS idx_combat_turns_timestamp ON combat_turns(timestamp);

-- =====================================================================
-- 6. Create abilities table
-- =====================================================================
CREATE TABLE IF NOT EXISTS abilities (
    id VARCHAR(36) PRIMARY KEY,
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

CREATE INDEX IF NOT EXISTS idx_abilities_character_id ON abilities(character_id);

-- =====================================================================
-- 7. Create messages table
-- =====================================================================
CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(36) PRIMARY KEY,
    campaign_id VARCHAR(36) NOT NULL,
    party_id VARCHAR(36) REFERENCES parties(id) ON DELETE SET NULL,
    sender_id VARCHAR(36) NOT NULL,
    sender_name VARCHAR(255) NOT NULL,
    message_type VARCHAR(50) NOT NULL DEFAULT 'chat',
    mode VARCHAR(10),
    content TEXT NOT NULL,
    attachment_url VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_campaign_id ON messages(campaign_id);
CREATE INDEX IF NOT EXISTS idx_messages_party_id ON messages(party_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- =====================================================================
-- 8. Create other supporting tables
-- =====================================================================

-- Echoes table (legacy)
CREATE TABLE IF NOT EXISTS echoes (
    id VARCHAR(36) PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    schema_type VARCHAR(100),
    payload JSON
);

-- Roll logs table
CREATE TABLE IF NOT EXISTS roll_logs (
    id SERIAL PRIMARY KEY,
    actor VARCHAR(255),
    target VARCHAR(255),
    roll_type VARCHAR(50),
    roll_mode VARCHAR(50),
    triggered_by VARCHAR(255),
    result JSON,
    modifiers JSON,
    session_id VARCHAR(36),
    encounter_id VARCHAR(36)
);

SELECT '✅ Base schema created successfully!' AS status;
