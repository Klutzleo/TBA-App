-- 012_campaign_stats.sql
-- Per-campaign aggregate stats table

CREATE TABLE IF NOT EXISTS campaign_stats (
    campaign_id       UUID PRIMARY KEY REFERENCES campaigns(id) ON DELETE CASCADE,
    total_rolls       BIGINT NOT NULL DEFAULT 0,
    total_ones        BIGINT NOT NULL DEFAULT 0,
    total_attacks     BIGINT NOT NULL DEFAULT 0,
    total_damage_dealt BIGINT NOT NULL DEFAULT 0,
    biggest_hit       INT    NOT NULL DEFAULT 0,
    total_callings    BIGINT NOT NULL DEFAULT 0,
    total_messages    BIGINT NOT NULL DEFAULT 0,
    total_battles     BIGINT NOT NULL DEFAULT 0,
    updated_at        TIMESTAMP DEFAULT NOW()
);
