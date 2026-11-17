-- Rules v3.1 Ascension: from level 11 each ability slot gains a secondary effect (slot 1 at level 11 up to slot 5 at 15).
-- Stored as JSON: {kind: debuff|buff|note, stat: pp|ip|sp, strength: 1-4, note: text}. Additive only; safe to re-run.

ALTER TABLE abilities ADD COLUMN IF NOT EXISTS secondary_effect JSONB;
