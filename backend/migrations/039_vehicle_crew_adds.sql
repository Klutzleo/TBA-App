-- Vehicles V3 (rules v3.1.1): a Captain's or Pilot's support roll waits here until the Gunner's (or Defense Officer's) next roll
-- uses it. One pending add per support station. Additive only; safe to re-run.

CREATE TABLE IF NOT EXISTS vehicle_crew_adds (
    id UUID PRIMARY KEY,
    vehicle_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    station VARCHAR(20) NOT NULL,
    target VARCHAR(10) NOT NULL,
    amount INTEGER NOT NULL,
    note VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_vehicle_crew_add_station UNIQUE (vehicle_id, station)
);

CREATE INDEX IF NOT EXISTS ix_vehicle_crew_adds_vehicle_id ON vehicle_crew_adds (vehicle_id);
