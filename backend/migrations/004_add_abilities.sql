-- Migration 004: Create Abilities Table
-- Phase 2d: Custom spells, techniques, and abilities for characters
--
-- Purpose: Store character-specific abilities (spells, techniques, special moves)
-- Each character can have up to 5 ability slots with custom macros
-- Examples: /fireball, /slash, /heal, /persuade, /stealth

CREATE TABLE IF NOT EXISTS abilities (
    id VARCHAR PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),  -- UUID-like string
    character_id VARCHAR NOT NULL,
    slot_number INTEGER NOT NULL CHECK (slot_number >= 1 AND slot_number <= 5),  -- 1-5 ability slots

    -- Ability identification
    ability_type VARCHAR(20) NOT NULL CHECK (ability_type IN ('spell', 'technique', 'special')),
    display_name VARCHAR(100) NOT NULL,  -- e.g., "Fireball", "Slash", "Persuade"
    macro_command VARCHAR(50) NOT NULL,  -- e.g., "/fireball", "/slash", "/persuade"

    -- Ability mechanics
    power_source VARCHAR(10) NOT NULL CHECK (power_source IN ('PP', 'IP', 'SP')),  -- Which stat powers this ability
    effect_type VARCHAR(20) NOT NULL CHECK (effect_type IN ('damage', 'heal', 'buff', 'debuff', 'utility')),
    die VARCHAR(10) NOT NULL,  -- Dice expression: "2d6", "3d4", "1d12"
    is_aoe BOOLEAN NOT NULL DEFAULT FALSE,  -- Whether ability affects multiple targets

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_abilities_character_id ON abilities(character_id);
CREATE INDEX IF NOT EXISTS idx_abilities_slot ON abilities(slot_number);

-- Create unique constraint: Character can only have one ability per slot
CREATE UNIQUE INDEX IF NOT EXISTS idx_abilities_character_slot
    ON abilities(character_id, slot_number);

-- Create unique constraint: Character can't have duplicate macro commands
CREATE UNIQUE INDEX IF NOT EXISTS idx_abilities_character_macro
    ON abilities(character_id, macro_command);

-- Add comments for documentation (PostgreSQL only)
-- COMMENT ON TABLE abilities IS 'Custom spells, techniques, and abilities for characters';
-- COMMENT ON COLUMN abilities.slot_number IS 'Ability slot (1-5), determines hotkey/UI position';
-- COMMENT ON COLUMN abilities.ability_type IS 'Category: spell (magical), technique (martial), special (unique)';
-- COMMENT ON COLUMN abilities.display_name IS 'Human-readable name shown in UI';
-- COMMENT ON COLUMN abilities.macro_command IS 'Chat command to trigger ability (e.g., /fireball)';
-- COMMENT ON COLUMN abilities.power_source IS 'Which stat powers this ability: PP, IP, or SP';
-- COMMENT ON COLUMN abilities.effect_type IS 'Effect category: damage, heal, buff, debuff, or utility';
-- COMMENT ON COLUMN abilities.die IS 'Dice expression for ability roll (e.g., 2d6, 3d4)';
-- COMMENT ON COLUMN abilities.is_aoe IS 'Whether ability affects multiple targets (area of effect)';

-- Migration complete
SELECT 'Migration 004: Abilities table created successfully' AS status;
