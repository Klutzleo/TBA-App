-- Migration 007: Inventory v2 — loot pool + equipment slots

-- Make character_id nullable: NULL = item lives in SW loot pool
ALTER TABLE inventory_items ALTER COLUMN character_id DROP NOT NULL;

-- Track whether a piece of equipment is currently equipped
ALTER TABLE inventory_items
    ADD COLUMN IF NOT EXISTS is_equipped BOOLEAN NOT NULL DEFAULT FALSE;

-- Which roll the bonus affects: 'attack' | 'defense' | NULL (no mechanical bonus)
ALTER TABLE inventory_items
    ADD COLUMN IF NOT EXISTS bonus_type VARCHAR(20);

-- Fast lookup for loot pool items (character_id IS NULL)
CREATE INDEX IF NOT EXISTS idx_inventory_loot_pool
    ON inventory_items(campaign_id)
    WHERE character_id IS NULL;

-- item_type now supports: consumable | key_item | quest_item | equipment | misc
-- effect_type now supports: heal | buff | damage | other
-- (VARCHAR columns — no schema change needed, validation is at the app layer)
