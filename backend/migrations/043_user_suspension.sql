-- Admin center, phase C: record when and why an account was suspended. users.is_active already exists and is already enforced at login and on
-- every authenticated request; these two columns are the admin's record. Additive only; safe to re-run.

ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suspension_reason VARCHAR(300);
