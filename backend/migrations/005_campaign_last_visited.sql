-- Track when each user last visited each campaign
-- Used to compute unread message counts on the campaign management screen

CREATE TABLE IF NOT EXISTS campaign_last_visited (
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    campaign_id UUID        NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    visited_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, campaign_id)
);
