-- Campaign cover: which vertical slice of the image shows in the thin header / card crop (0 top .. 100 bottom).
-- Additive only; existing covers default to the middle.

ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS banner_focus_y INTEGER NOT NULL DEFAULT 50;
