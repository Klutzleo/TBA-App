-- Migration 020: Discord live mirror + reaction hype
-- Mirroring is "on" for a campaign iff discord_channel_id is non-null — no separate
-- enabled flag, avoids enabled=true/channel_id=null drift.

ALTER TABLE campaigns
  ADD COLUMN IF NOT EXISTS discord_channel_id VARCHAR(32) NULL;

CREATE TABLE IF NOT EXISTS discord_mirrored_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL,
    discord_channel_id VARCHAR(32) NOT NULL,
    discord_message_id VARCHAR(32) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    source_message_id UUID NULL,
    posted_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_discord_mirrored_messages_campaign_posted
    ON discord_mirrored_messages (campaign_id, posted_at);

CREATE INDEX IF NOT EXISTS idx_discord_mirrored_messages_source
    ON discord_mirrored_messages (source_message_id);

CREATE TABLE IF NOT EXISTS discord_reaction_counts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mirrored_message_id UUID NOT NULL REFERENCES discord_mirrored_messages(id) ON DELETE CASCADE,
    emoji_key VARCHAR(80) NOT NULL,
    last_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (mirrored_message_id, emoji_key)
);
