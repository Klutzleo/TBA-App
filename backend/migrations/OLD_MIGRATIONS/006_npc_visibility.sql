-- Add visible_to_players flag to characters table for NPCs
-- SW controls which NPCs players can see/target; default FALSE (hidden)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS visible_to_players BOOLEAN NOT NULL DEFAULT FALSE;
