-- 018_bonds.sql
-- Bonds system: character relationships + combo tracking

CREATE TABLE IF NOT EXISTS bonds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    character_id_a UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    character_id_b UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    combo_name VARCHAR(100),
    combo_description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    broken_at TIMESTAMP,
    broken_by_user_id UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_bonds_campaign ON bonds(campaign_id);
CREATE INDEX IF NOT EXISTS idx_bonds_char_a ON bonds(character_id_a);
CREATE INDEX IF NOT EXISTS idx_bonds_char_b ON bonds(character_id_b);

-- Pending combos: ephemeral to an encounter, cleared on encounter end
CREATE TABLE IF NOT EXISTS pending_combos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id UUID NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    bond_id UUID REFERENCES bonds(id) ON DELETE SET NULL,
    proposer_character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    acceptor_character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    -- status: pending → accepted/holding → ready → fired/declined/cancelled
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    proposer_ability_slot INTEGER,  -- locked in when combo fires
    acceptor_ability_slot INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_combos_encounter ON pending_combos(encounter_id);
CREATE INDEX IF NOT EXISTS idx_pending_combos_proposer ON pending_combos(proposer_character_id);
CREATE INDEX IF NOT EXISTS idx_pending_combos_acceptor ON pending_combos(acceptor_character_id);
