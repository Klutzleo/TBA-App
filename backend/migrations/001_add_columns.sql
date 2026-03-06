-- 001_add_columns.sql
-- Adds new columns introduced after the initial clean-start migration.
-- Safe to run multiple times (IF NOT EXISTS / EXCEPTION guards).

DO $$ BEGIN
    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ;
EXCEPTION
    WHEN duplicate_column THEN null;
END $$;

DO $$ BEGIN
    ALTER TABLE characters ADD COLUMN IF NOT EXISTS battle_scars JSON DEFAULT '[]';
EXCEPTION
    WHEN duplicate_column THEN null;
END $$;

DO $$ BEGIN
    ALTER TABLE characters ADD COLUMN IF NOT EXISTS has_faced_calling_this_encounter BOOLEAN NOT NULL DEFAULT FALSE;
EXCEPTION
    WHEN duplicate_column THEN null;
END $$;

DO $$ BEGIN
    ALTER TABLE characters ADD COLUMN IF NOT EXISTS tethers JSON DEFAULT '[]';
EXCEPTION
    WHEN duplicate_column THEN null;
END $$;

DO $$ BEGIN
    ALTER TABLE characters ADD COLUMN IF NOT EXISTS active_tether_modifier INTEGER NOT NULL DEFAULT 0;
EXCEPTION
    WHEN duplicate_column THEN null;
END $$;

CREATE TABLE IF NOT EXISTS memory_echoes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id) ON DELETE SET NULL,
    character_name VARCHAR(200) NOT NULL,
    echo_text TEXT NOT NULL,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memory_echoes_campaign ON memory_echoes(campaign_id);

SELECT '001_add_columns: done' AS status;
