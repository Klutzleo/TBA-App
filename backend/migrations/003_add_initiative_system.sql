-- Migration: Add Initiative & Encounter System
-- Creates encounters and initiative_rolls tables for combat tracking

-- Create encounters table
CREATE TABLE IF NOT EXISTS encounters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_encounters_campaign ON encounters(campaign_id);
CREATE INDEX IF NOT EXISTS idx_encounters_active ON encounters(campaign_id, is_active);

-- Create initiative_rolls table
CREATE TABLE IF NOT EXISTS initiative_rolls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id UUID NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    npc_id UUID REFERENCES npcs(id) ON DELETE CASCADE,

    name VARCHAR NOT NULL,  -- Cached display name
    roll_result INTEGER NOT NULL,
    is_silent BOOLEAN NOT NULL DEFAULT FALSE,  -- Hidden from players
    rolled_by_sw BOOLEAN NOT NULL DEFAULT FALSE,  -- Forced roll vs self-roll

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT check_one_entity CHECK (
        (character_id IS NOT NULL AND npc_id IS NULL) OR
        (character_id IS NULL AND npc_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_initiative_encounter ON initiative_rolls(encounter_id);
CREATE INDEX IF NOT EXISTS idx_initiative_character ON initiative_rolls(character_id);
CREATE INDEX IF NOT EXISTS idx_initiative_npc ON initiative_rolls(npc_id);
CREATE INDEX IF NOT EXISTS idx_initiative_order ON initiative_rolls(encounter_id, roll_result DESC);
