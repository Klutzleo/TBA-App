-- Vehicles (rules v3.1.1): a vehicle is a Character row (is_npc + is_vehicle, like Objects) with its own table numbers, and a
-- crew table says who holds which station. Additive only; safe to re-run.

ALTER TABLE characters ADD COLUMN IF NOT EXISTS is_vehicle BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS vehicle_kind VARCHAR(10) NOT NULL DEFAULT 'enclosed';

CREATE TABLE IF NOT EXISTS vehicle_crew (
    id UUID PRIMARY KEY,
    vehicle_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    station VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_vehicle_crew_station UNIQUE (vehicle_id, station),
    CONSTRAINT uq_vehicle_crew_character UNIQUE (character_id)
);

CREATE INDEX IF NOT EXISTS ix_vehicle_crew_vehicle_id ON vehicle_crew (vehicle_id);
CREATE INDEX IF NOT EXISTS ix_vehicle_crew_character_id ON vehicle_crew (character_id);
