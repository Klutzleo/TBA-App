-- Add portrait_url column to characters table
ALTER TABLE characters ADD COLUMN IF NOT EXISTS portrait_url VARCHAR;
