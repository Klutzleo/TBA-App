-- Migration 024: Objects (locks / doors / chests / terminals / traps / seals).
-- An Object is a `characters` row with is_npc=TRUE AND is_object=TRUE.
--   is_npc=TRUE  -> inherits the NPC contract (no user_id, The Calling guards skip it,
--                  DP floors at 0, "knocked out" line, excluded from PC stat trackers).
--   is_object=TRUE -> exclusion marker that keeps it off every NPC surface
--                  (bubble bar, @-mentions, Stat/Env/Encounter modal NPC rows) via a
--                  single `is_object = FALSE` filter added to list_npcs.
-- check_difficulty : "1d10|Hard" (die|label) — the tier a player rolls their stat against.
--                    NULL = smash-only (no lock to pick).
-- check_stats      : "PP,IP,SP" subset — which stats the SW allows against it. NULL = any.
-- dp / max_dp      : reused as the smash pool. max_dp = 0 means "can't be smashed".
-- object_revealed  : flipped once when the Object is beaten (check win OR DP->0); contents
--                    become visible; guards against a double reveal.
-- Additive only — ADD COLUMN IF NOT EXISTS, safe to re-run.

ALTER TABLE characters
  ADD COLUMN IF NOT EXISTS is_object        BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE characters
  ADD COLUMN IF NOT EXISTS check_difficulty VARCHAR(24);

ALTER TABLE characters
  ADD COLUMN IF NOT EXISTS check_stats      VARCHAR(12);

ALTER TABLE characters
  ADD COLUMN IF NOT EXISTS object_revealed  BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS ix_characters_is_object ON characters (is_object);

ALTER TABLE stat_check_requests
  ADD COLUMN IF NOT EXISTS object_id UUID REFERENCES characters(id) ON DELETE SET NULL;
