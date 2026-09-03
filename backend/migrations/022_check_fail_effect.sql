-- Migration 022: optional buff/debuff applied to whoever FAILS a Stat / Env check.
-- Damage is still automatic (the difference); this is for "and you're also -1 IP
-- for 2 rounds" style consequences the SW sets in the modal.
-- Additive only — ADD COLUMN IF NOT EXISTS, safe to re-run.

ALTER TABLE stat_check_requests
  ADD COLUMN IF NOT EXISTS fail_effect JSONB;   -- {name, modifier, modifier_type, duration_rounds} or NULL
