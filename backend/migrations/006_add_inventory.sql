-- Migration 006: Inventory system + currency

-- Currency amount per character
ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS currency INTEGER NOT NULL DEFAULT 0;

-- SW-named currency (e.g. "Gold", "Credits", "Chips") per campaign
ALTER TABLE campaigns
    ADD COLUMN IF NOT EXISTS currency_name VARCHAR(50) NOT NULL DEFAULT 'Gold';

-- Inventory items
CREATE TABLE IF NOT EXISTS inventory_items (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID         NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    campaign_id  UUID         NOT NULL REFERENCES campaigns(id)  ON DELETE CASCADE,
    name         VARCHAR(100) NOT NULL,
    item_type    VARCHAR(20)  NOT NULL DEFAULT 'misc',  -- consumable | key_item | equipment | misc
    quantity     INTEGER      NOT NULL DEFAULT 1,
    description  TEXT,
    tier         INTEGER,                               -- 1-6 (consumables only)
    effect_type  VARCHAR(20),                           -- heal | buff | other (consumables only)
    bonus        INTEGER,                               -- flat bonus for equipment (+1, +2...)
    given_by_sw  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inventory_character ON inventory_items(character_id);
CREATE INDEX IF NOT EXISTS idx_inventory_campaign  ON inventory_items(campaign_id);
