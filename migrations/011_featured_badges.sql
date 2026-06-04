-- 011_featured_badges.sql
-- Stores up to 5 featured achievement IDs on a user's profile.
-- Slots unlock at points thresholds: 3 at 150, 4 at 300, 5 at 500.

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS featured_badges JSONB NOT NULL DEFAULT '[]'::jsonb;
