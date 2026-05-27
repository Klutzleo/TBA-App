-- Player stats system: user_stats, character_stats, site_stats

-- ============================================================
-- user_stats — lifetime totals per user across all campaigns
-- ============================================================
CREATE TABLE IF NOT EXISTS user_stats (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,

    -- Dice
    total_rolls         INTEGER NOT NULL DEFAULT 0,
    total_ones          INTEGER NOT NULL DEFAULT 0,   -- rolled a 1 (any die)
    total_max_rolls     INTEGER NOT NULL DEFAULT 0,   -- rolled max possible on a die
    total_stat_checks   INTEGER NOT NULL DEFAULT 0,
    total_pp_checks     INTEGER NOT NULL DEFAULT 0,
    total_ip_checks     INTEGER NOT NULL DEFAULT 0,
    total_sp_checks     INTEGER NOT NULL DEFAULT 0,
    total_initiatives   INTEGER NOT NULL DEFAULT 0,

    -- Combat
    total_attacks           INTEGER NOT NULL DEFAULT 0,
    total_damage_dealt      INTEGER NOT NULL DEFAULT 0,
    total_damage_taken      INTEGER NOT NULL DEFAULT 0,
    total_abilities_cast    INTEGER NOT NULL DEFAULT 0,
    biggest_hit_dealt       INTEGER NOT NULL DEFAULT 0,
    biggest_hit_taken       INTEGER NOT NULL DEFAULT 0,
    battles_survived        INTEGER NOT NULL DEFAULT 0,

    -- Drama
    total_callings          INTEGER NOT NULL DEFAULT 0,
    total_battle_scars      INTEGER NOT NULL DEFAULT 0,

    -- Boosts
    total_bap_used          INTEGER NOT NULL DEFAULT 0,
    total_tethers_invoked   INTEGER NOT NULL DEFAULT 0,
    total_boosts_applied    INTEGER NOT NULL DEFAULT 0,

    -- Social
    total_messages_sent     INTEGER NOT NULL DEFAULT 0,
    campaigns_joined        INTEGER NOT NULL DEFAULT 0,

    -- Time
    first_played_at     TIMESTAMPTZ,
    last_played_at      TIMESTAMPTZ,
    total_play_minutes  INTEGER NOT NULL DEFAULT 0,

    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- character_stats — same breakdown per character
-- ============================================================
CREATE TABLE IF NOT EXISTS character_stats (
    character_id    UUID PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    total_rolls         INTEGER NOT NULL DEFAULT 0,
    total_ones          INTEGER NOT NULL DEFAULT 0,
    total_max_rolls     INTEGER NOT NULL DEFAULT 0,
    total_stat_checks   INTEGER NOT NULL DEFAULT 0,
    total_pp_checks     INTEGER NOT NULL DEFAULT 0,
    total_ip_checks     INTEGER NOT NULL DEFAULT 0,
    total_sp_checks     INTEGER NOT NULL DEFAULT 0,
    total_initiatives   INTEGER NOT NULL DEFAULT 0,

    total_attacks           INTEGER NOT NULL DEFAULT 0,
    total_damage_dealt      INTEGER NOT NULL DEFAULT 0,
    total_damage_taken      INTEGER NOT NULL DEFAULT 0,
    total_abilities_cast    INTEGER NOT NULL DEFAULT 0,
    biggest_hit_dealt       INTEGER NOT NULL DEFAULT 0,
    biggest_hit_taken       INTEGER NOT NULL DEFAULT 0,
    battles_survived        INTEGER NOT NULL DEFAULT 0,

    total_callings          INTEGER NOT NULL DEFAULT 0,
    total_battle_scars      INTEGER NOT NULL DEFAULT 0,

    total_bap_used          INTEGER NOT NULL DEFAULT 0,
    total_tethers_invoked   INTEGER NOT NULL DEFAULT 0,
    total_boosts_applied    INTEGER NOT NULL DEFAULT 0,

    total_messages_sent     INTEGER NOT NULL DEFAULT 0,

    first_played_at     TIMESTAMPTZ,
    last_played_at      TIMESTAMPTZ,

    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_character_stats_user ON character_stats(user_id);

-- ============================================================
-- site_stats — singleton row for global boast bar
-- ============================================================
CREATE TABLE IF NOT EXISTS site_stats (
    id                  INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    total_rolls         BIGINT NOT NULL DEFAULT 0,
    total_ones          BIGINT NOT NULL DEFAULT 0,
    total_max_rolls     BIGINT NOT NULL DEFAULT 0,
    total_attacks       BIGINT NOT NULL DEFAULT 0,
    total_damage_dealt  BIGINT NOT NULL DEFAULT 0,
    total_callings      BIGINT NOT NULL DEFAULT 0,
    total_messages      BIGINT NOT NULL DEFAULT 0,
    total_battles       BIGINT NOT NULL DEFAULT 0,
    total_players       BIGINT NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure the singleton row exists
INSERT INTO site_stats (id) VALUES (1) ON CONFLICT DO NOTHING;

-- ============================================================
-- user profile settings (privacy, bio, discord link)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    bio             TEXT,
    is_public       BOOLEAN NOT NULL DEFAULT TRUE,
    discord_id      VARCHAR(32),
    discord_username VARCHAR(64),
    avatar_url      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
