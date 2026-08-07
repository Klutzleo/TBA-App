-- Migration 019: Track when the SW rolled a stat check on the player's behalf
-- (e.g. player AFK/unresponsive) — same concept as initiative_rolls.rolled_by_sw.
-- Also doubles as a record an SW can point to when a player is consistently unresponsive.

ALTER TABLE stat_check_requests
  ADD COLUMN IF NOT EXISTS rolled_by_sw BOOLEAN NOT NULL DEFAULT FALSE;
