-- Migration 008: Web Push subscriptions for PWA notifications

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint     TEXT         NOT NULL,
    p256dh       TEXT         NOT NULL,   -- browser public key
    auth         TEXT         NOT NULL,   -- browser auth secret
    campaign_id  UUID         REFERENCES campaigns(id) ON DELETE CASCADE,  -- NULL = global, set = campaign-scoped
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMP,

    -- One subscription per endpoint per user (upsert-safe)
    UNIQUE(user_id, endpoint)
);

CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user    ON push_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_campaign ON push_subscriptions(campaign_id);
