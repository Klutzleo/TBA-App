-- 026_triple_combo.sql
-- Triple Combo: 3-way bonded combo attacks. Requires bilateral Bonds between all
-- 3 characters (A-B, A-C, B-C) and all 3 at level 10. Additive — does not touch
-- pending_combos or bonds (the 2-person system stays untouched). Safe to re-run.

CREATE TABLE IF NOT EXISTS pending_triple_combos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id UUID NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,

    bond_ab_id UUID REFERENCES bonds(id) ON DELETE SET NULL,
    bond_ac_id UUID REFERENCES bonds(id) ON DELETE SET NULL,
    bond_bc_id UUID REFERENCES bonds(id) ON DELETE SET NULL,

    proposer_character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    partner_a_character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    partner_b_character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,

    partner_a_accepted_at TIMESTAMP,
    partner_b_accepted_at TIMESTAMP,
    -- set once the 2nd of {partner_a, partner_b} accepts — their own next turn
    -- fires the combo; the proposer + the other (first-accepting) partner hold
    last_acceptor_character_id UUID REFERENCES characters(id) ON DELETE CASCADE,

    -- status: pending -> accepted_by_one -> holding -> ready -> fired/declined/cancelled
    status VARCHAR(20) NOT NULL DEFAULT 'pending',

    proposer_ability_slot INTEGER,
    partner_a_ability_slot INTEGER,
    partner_b_ability_slot INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_triple_combos_encounter ON pending_triple_combos(encounter_id);
CREATE INDEX IF NOT EXISTS idx_pending_triple_combos_proposer ON pending_triple_combos(proposer_character_id);
CREATE INDEX IF NOT EXISTS idx_pending_triple_combos_partner_a ON pending_triple_combos(partner_a_character_id);
CREATE INDEX IF NOT EXISTS idx_pending_triple_combos_partner_b ON pending_triple_combos(partner_b_character_id);
