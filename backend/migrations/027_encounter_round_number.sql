-- 027_encounter_round_number.sql
-- Initiative rounds: encounters.round_number starts at 1 and goes up each time the turn
-- order wraps back to the top. Additive and backward compatible: existing rows (including an
-- encounter that is running during the deploy) simply read as round 1. Safe to re-run.

ALTER TABLE encounters ADD COLUMN IF NOT EXISTS round_number INTEGER NOT NULL DEFAULT 1;
