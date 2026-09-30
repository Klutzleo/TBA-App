-- LBA ("Lore for the Bad-Ass" / "Lore for Being Awesome") Stage 0.
-- New table, unrelated to lore_entries (which stays the private per-campaign
-- notes tab, untouched). See plan doc for full design.

CREATE TABLE IF NOT EXISTS lba_packages (
    id                      UUID PRIMARY KEY,
    author_user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    co_author_user_ids      JSONB NOT NULL DEFAULT '[]',

    title                   VARCHAR(200) NOT NULL,
    tagline                 VARCHAR(300),
    format                  VARCHAR(20) NOT NULL DEFAULT 'one_shot',
    suggested_party_size    VARCHAR(20),
    content_rating          VARCHAR(20) NOT NULL DEFAULT 'all_ages',
    tags                    JSONB NOT NULL DEFAULT '[]',
    is_public               BOOLEAN NOT NULL DEFAULT false,
    view_count              INTEGER NOT NULL DEFAULT 0,
    adoption_count          INTEGER NOT NULL DEFAULT 0,

    homebrew_note           TEXT,
    story_text              TEXT,
    world_text              TEXT,
    core_npc_character_ids  JSONB NOT NULL DEFAULT '[]',
    core_item_ids           JSONB NOT NULL DEFAULT '[]',
    side_quests             JSONB NOT NULL DEFAULT '[]',
    attachments             JSONB NOT NULL DEFAULT '[]',

    created_at              TIMESTAMP DEFAULT now(),
    updated_at              TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_lba_packages_author_user_id ON lba_packages(author_user_id);
CREATE INDEX IF NOT EXISTS ix_lba_packages_is_public ON lba_packages(is_public);
