-- Active Effects table for buff/debuff tracking
CREATE TABLE IF NOT EXISTS active_effects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    modifier INTEGER NOT NULL DEFAULT 0,
    modifier_type VARCHAR(20) NOT NULL DEFAULT 'custom',
    duration_rounds INTEGER,
    applied_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_active_effects_campaign ON active_effects(campaign_id);
CREATE INDEX IF NOT EXISTS idx_active_effects_character ON active_effects(character_id);
