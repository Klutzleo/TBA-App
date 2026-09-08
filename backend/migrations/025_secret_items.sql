-- Migration 025: secret items.
-- secret = the SW stashed this item quietly (typically inside an Object). The item
--   still exists and transfers normally, but every "look what you got!" surface is
--   muted: no chat announcement on add, no gift toast on give. SW-facing lists mark
--   it with a 🤫 so the SW still sees it plainly.
-- Additive only — ADD COLUMN IF NOT EXISTS, safe to re-run.

ALTER TABLE inventory_items
  ADD COLUMN IF NOT EXISTS secret BOOLEAN NOT NULL DEFAULT FALSE;
