-- Email digest notifications (your turn / @mention), max twice a day, opt-out.
-- last_login already exists as a column (000_CLEAN_START.sql) — no migration needed there,
-- it was just never mapped in the ORM (fixed in backend/models.py).

ALTER TABLE notifications ADD COLUMN IF NOT EXISTS emailed_at TIMESTAMPTZ;

ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS email_notifications_enabled BOOLEAN NOT NULL DEFAULT true;
