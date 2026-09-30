-- LBA: genre as its own structured, multi-value, filterable field, separate
-- from the free-tag list. Teaser-tier (public, no login) like format/party
-- size/content rating.

ALTER TABLE lba_packages ADD COLUMN IF NOT EXISTS genres JSONB NOT NULL DEFAULT '[]';
