-- Campaign browse tags (genres + content rating) and the "Based on" credit for campaigns started
-- from an LBA story. Additive only; all columns nullable or defaulted.

ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS genres JSONB NOT NULL DEFAULT '[]';
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS content_rating VARCHAR(20);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS source_package_id UUID REFERENCES lba_packages(id) ON DELETE SET NULL;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS source_title VARCHAR(200);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS source_author_user_id UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS show_source_in_game BOOLEAN NOT NULL DEFAULT false;
