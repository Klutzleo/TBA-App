-- 010_notifications.sql
-- Notification center — drives both the drawer and toast popups.
-- is_permanent = never clearable (Hall of Fame / Hall of Shame)
-- shame        = routes to Hall of Shame instead of Hall of Fame
-- silent       = row created but no toast fired (used for retroactive sweep)

CREATE TABLE IF NOT EXISTS notifications (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type         VARCHAR(30)  NOT NULL,   -- achievement / level_up / whisper / invite / mention / approval / system
    title        VARCHAR(200) NOT NULL,
    body         TEXT,
    icon         VARCHAR(50),             -- Lucide icon name
    data         JSONB,                   -- type-specific payload (achievement_id, campaign_id, etc)
    is_permanent BOOLEAN NOT NULL DEFAULT FALSE,
    shame        BOOLEAN NOT NULL DEFAULT FALSE,
    silent       BOOLEAN NOT NULL DEFAULT FALSE,
    read         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id    ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, read) WHERE read = FALSE;
CREATE INDEX IF NOT EXISTS idx_notifications_created    ON notifications(user_id, created_at DESC);
