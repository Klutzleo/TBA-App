-- Rules v3.1: a spell or technique can heal the same character only once per encounter.
-- One row per (encounter, healed character). Cleared when the encounter ends. Additive only; safe to re-run.

CREATE TABLE IF NOT EXISTS encounter_heals (
    id UUID PRIMARY KEY,
    encounter_id UUID NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    target_character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    healer_character_id UUID REFERENCES characters(id) ON DELETE SET NULL,
    ability_name VARCHAR(100),
    amount INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_encounter_heal_target UNIQUE (encounter_id, target_character_id)
);

CREATE INDEX IF NOT EXISTS ix_encounter_heals_encounter_id ON encounter_heals (encounter_id);
CREATE INDEX IF NOT EXISTS ix_encounter_heals_target_character_id ON encounter_heals (target_character_id);
