-- Migration 015: Stat check request tracking table

CREATE TABLE IF NOT EXISTS stat_check_requests (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id      UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    character_id     UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    stat             VARCHAR(2) NOT NULL,
    difficulty_die   VARCHAR(8) NOT NULL,
    difficulty_label VARCHAR(20) NOT NULL,
    sw_roll          INTEGER NOT NULL,
    flavor_text      TEXT,
    bap_granted      BOOLEAN NOT NULL DEFAULT FALSE,
    status           VARCHAR(10) NOT NULL DEFAULT 'pending',
    player_roll      INTEGER,
    player_total     INTEGER,
    outcome          VARCHAR(4),
    margin           INTEGER,
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at      TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_stat_check_campaign ON stat_check_requests(campaign_id);
CREATE INDEX IF NOT EXISTS idx_stat_check_character ON stat_check_requests(character_id);
CREATE INDEX IF NOT EXISTS idx_stat_check_status ON stat_check_requests(campaign_id, status);
