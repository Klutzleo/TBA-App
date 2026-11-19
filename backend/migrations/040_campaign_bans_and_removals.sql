-- Admin center, phase A: a Story Weaver can remove a player from a campaign and optionally ban them from it.
-- Removal is recorded on the membership row (left_at is already how a departure is stored). A ban is its own row so the join code can refuse
-- someone who was removed. Additive only; safe to re-run.

ALTER TABLE campaign_memberships ADD COLUMN IF NOT EXISTS removed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE campaign_memberships ADD COLUMN IF NOT EXISTS removal_reason VARCHAR(300);

CREATE TABLE IF NOT EXISTS campaign_bans (
    id UUID PRIMARY KEY,
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    banned_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reason VARCHAR(300),
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_campaign_ban UNIQUE (campaign_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_campaign_bans_campaign_id ON campaign_bans (campaign_id);
CREATE INDEX IF NOT EXISTS ix_campaign_bans_user_id ON campaign_bans (user_id);
