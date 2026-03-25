-- Summon system: track summon abilities and summon NPCs
ALTER TABLE abilities ADD COLUMN IF NOT EXISTS is_summon BOOLEAN DEFAULT FALSE;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS is_summon BOOLEAN DEFAULT FALSE;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS summoner_id UUID REFERENCES characters(id) ON DELETE SET NULL;
