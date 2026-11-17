-- Damage Effects (poison, burning, bleeding; rules v3.1) are stored as an active effect with modifier_type 'dot'.
-- This column holds what they need when they fire: {die, stat, caster, ability}. Additive only; safe to re-run.

ALTER TABLE active_effects ADD COLUMN IF NOT EXISTS data JSONB;
