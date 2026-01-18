# Phase 2d Migrations: Tab System & Character Abilities

## Overview

These migrations implement the **Phase 2d: MVP with character creation and tab system** features for the TBA Digital Companion App. They add database schema support for:

1. **Party/Tab System** - Story, OOC, Standard, and Whisper chat tabs
2. **Party Membership** - Dynamic character-to-party associations
3. **Character Enhancements** - Notes, status, equipment bonuses, uses per encounter
4. **Custom Abilities** - Spells, techniques, and special moves with macro commands
5. **Message Routing** - Tab-based message organization

---

## Migration Files

### 001_add_parties.sql - Party/Tab System

**Purpose:** Create the `parties` table for organizing campaign chat into tabs.

**Schema:**
```sql
CREATE TABLE parties (
    id VARCHAR PRIMARY KEY,
    campaign_id VARCHAR NOT NULL,
    name VARCHAR(100) NOT NULL,
    party_type VARCHAR(20) CHECK (party_type IN ('story', 'ooc', 'standard', 'whisper')),
    is_active BOOLEAN DEFAULT TRUE,
    archived_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Features:**
- **Unique constraint:** Only one `'story'` party per campaign
- **Unique constraint:** Only one `'ooc'` party per campaign
- **Indexes:** `campaign_id`, `party_type`, `is_active`
- **Soft deletes:** `archived_at` timestamp instead of hard deletes

**Party Types:**
- `'story'` - Main in-character (IC) campaign tab (required, one per campaign)
- `'ooc'` - Out-of-character discussion tab (required, one per campaign)
- `'standard'` - Custom channels/groups (unlimited)
- `'whisper'` - Private DM channels (unlimited)

**Example Usage:**
```sql
-- Create Story tab for campaign
INSERT INTO parties (id, campaign_id, name, party_type)
VALUES ('uuid-1', 'campaign-123', 'The Fellowship', 'story');

-- Create OOC tab
INSERT INTO parties (id, campaign_id, name, party_type)
VALUES ('uuid-2', 'campaign-123', 'Out of Character', 'ooc');

-- Create custom side quest tab
INSERT INTO parties (id, campaign_id, name, party_type, is_active)
VALUES ('uuid-3', 'campaign-123', 'Side Quest: Goblin Cave', 'standard', TRUE);
```

---

### 002_add_party_members.sql - Party Membership

**Purpose:** Track which characters belong to which parties/tabs.

**Schema:**
```sql
CREATE TABLE party_members (
    id VARCHAR PRIMARY KEY,
    party_id VARCHAR NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    character_id VARCHAR NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP NULL
);
```

**Key Features:**
- **Cascade deletes:** If party or character is deleted, memberships are removed
- **Unique constraint:** Character can only be in a party once at a time (`left_at IS NULL`)
- **Indexes:** `party_id`, `character_id`, `left_at`
- **Soft leaves:** `left_at` timestamp tracks when character left (NULL = still active)

**Example Usage:**
```sql
-- Add Alice to Story tab
INSERT INTO party_members (id, party_id, character_id)
VALUES ('uuid-m1', 'uuid-1', 'alice-char-id');

-- Add Bob to Story tab
INSERT INTO party_members (id, party_id, character_id)
VALUES ('uuid-m2', 'uuid-1', 'bob-char-id');

-- Alice leaves the party
UPDATE party_members
SET left_at = CURRENT_TIMESTAMP
WHERE id = 'uuid-m1';

-- Query active members of a party
SELECT c.name
FROM party_members pm
JOIN characters c ON pm.character_id = c.id
WHERE pm.party_id = 'uuid-1' AND pm.left_at IS NULL;
```

---

### 003_update_characters.sql - Character Enhancements

**Purpose:** Add new fields to `characters` table for abilities, status tracking, and equipment.

**New Columns:**
```sql
ALTER TABLE characters ADD COLUMN notes TEXT NULL;
ALTER TABLE characters ADD COLUMN max_uses_per_encounter INTEGER DEFAULT 3;
ALTER TABLE characters ADD COLUMN current_uses INTEGER DEFAULT 3;
ALTER TABLE characters ADD COLUMN weapon_bonus INTEGER DEFAULT 0;
ALTER TABLE characters ADD COLUMN armor_bonus INTEGER DEFAULT 0;
ALTER TABLE characters ADD COLUMN times_called INTEGER DEFAULT 0;
ALTER TABLE characters ADD COLUMN is_called BOOLEAN DEFAULT FALSE;
ALTER TABLE characters ADD COLUMN status VARCHAR(20) DEFAULT 'active';
```

**Field Explanations:**

| Column | Purpose | Example Values |
|--------|---------|----------------|
| `notes` | Character backstory, personality, GM notes | "Brave but reckless. Fears spiders." |
| `max_uses_per_encounter` | Max uses for limited abilities | `3` (can use abilities 3 times per encounter) |
| `current_uses` | Remaining uses in current encounter | `1` (2 uses already spent) |
| `weapon_bonus` | Attack bonus from equipped weapon | `+2` (from "Longsword +2") |
| `armor_bonus` | Defense bonus from equipped armor | `+1` (from "Leather Armor +1") |
| `times_called` | How many times character/summon was called | `5` (summoned 5 times total) |
| `is_called` | Whether character is currently summoned | `TRUE` (currently active summon) |
| `status` | Character health status | `'active'`, `'unconscious'`, `'dead'` |

**Status Values:**
- `'active'` - Normal, can take actions
- `'unconscious'` - Downed, cannot act (0 DP)
- `'dead'` - Permanently dead (requires resurrection)

**Example Usage:**
```sql
-- Add notes to a character
UPDATE characters
SET notes = 'Alice is a brave warrior with a fear of heights. She lost her family to bandits.'
WHERE id = 'alice-char-id';

-- Character uses an ability (decrement uses)
UPDATE characters
SET current_uses = current_uses - 1
WHERE id = 'alice-char-id' AND current_uses > 0;

-- Reset uses at end of encounter
UPDATE characters
SET current_uses = max_uses_per_encounter
WHERE party_id = 'current-party-id';

-- Mark character as unconscious
UPDATE characters
SET status = 'unconscious'
WHERE id = 'alice-char-id';

-- Apply weapon bonus
UPDATE characters
SET weapon_bonus = 2
WHERE id = 'alice-char-id';
```

---

### 004_add_abilities.sql - Custom Abilities System

**Purpose:** Store character-specific spells, techniques, and abilities with macro commands.

**Schema:**
```sql
CREATE TABLE abilities (
    id VARCHAR PRIMARY KEY,
    character_id VARCHAR NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    slot_number INTEGER CHECK (slot_number >= 1 AND slot_number <= 5),
    ability_type VARCHAR(20) CHECK (ability_type IN ('spell', 'technique', 'special')),
    display_name VARCHAR(100) NOT NULL,
    macro_command VARCHAR(50) NOT NULL,
    power_source VARCHAR(10) CHECK (power_source IN ('PP', 'IP', 'SP')),
    effect_type VARCHAR(20) CHECK (effect_type IN ('damage', 'heal', 'buff', 'debuff', 'utility')),
    die VARCHAR(10) NOT NULL,
    is_aoe BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Features:**
- **5 Ability Slots:** Each character can have 1-5 abilities
- **Unique constraints:**
  - One ability per slot per character
  - No duplicate macro commands per character
- **Cascade deletes:** If character is deleted, abilities are removed
- **Indexes:** `character_id`, `slot_number`

**Field Explanations:**

| Column | Purpose | Example Values |
|--------|---------|----------------|
| `slot_number` | UI hotkey slot (1-5) | `1` (bound to F1 key) |
| `ability_type` | Category | `'spell'`, `'technique'`, `'special'` |
| `display_name` | Human-readable name | "Fireball", "Slash", "Persuade" |
| `macro_command` | Chat command | `/fireball`, `/slash`, `/persuade` |
| `power_source` | Stat that powers ability | `'PP'` (physical), `'IP'` (intellect), `'SP'` (social) |
| `effect_type` | What ability does | `'damage'`, `'heal'`, `'buff'`, `'debuff'`, `'utility'` |
| `die` | Dice expression | `"2d6"`, `"3d4"`, `"1d12"` |
| `is_aoe` | Affects multiple targets | `TRUE` (area of effect) |

**Example Abilities:**

```sql
-- Fireball (IP-based AOE damage spell)
INSERT INTO abilities (id, character_id, slot_number, ability_type, display_name, macro_command, power_source, effect_type, die, is_aoe)
VALUES ('ability-1', 'alice-char-id', 1, 'spell', 'Fireball', '/fireball', 'IP', 'damage', '3d6', TRUE);

-- Slash (PP-based single-target technique)
INSERT INTO abilities (id, character_id, slot_number, ability_type, display_name, macro_command, power_source, effect_type, die, is_aoe)
VALUES ('ability-2', 'alice-char-id', 2, 'technique', 'Slash', '/slash', 'PP', 'damage', '2d4', FALSE);

-- Heal (IP-based single-target healing spell)
INSERT INTO abilities (id, character_id, slot_number, ability_type, display_name, macro_command, power_source, effect_type, die, is_aoe)
VALUES ('ability-3', 'bob-char-id', 1, 'spell', 'Healing Touch', '/heal', 'IP', 'heal', '2d6', FALSE);

-- Persuade (SP-based utility technique)
INSERT INTO abilities (id, character_id, slot_number, ability_type, display_name, macro_command, power_source, effect_type, die, is_aoe)
VALUES ('ability-4', 'charlie-char-id', 1, 'technique', 'Persuade', '/persuade', 'SP', 'utility', '1d8', FALSE);
```

**Usage in Chat:**
```
Alice: /fireball @goblin1 @goblin2 @goblin3
Server: 🔥 Fireball (3d6 + IP + Edge) → 15 damage to 3 targets!

Bob: /slash @goblin1
Server: ⚔️ Slash (2d4 + PP + Edge) → 7 damage to Goblin!

Charlie: /persuade @merchant
Server: 🗣️ Persuade (1d8 + SP + Edge) → 9. Merchant is convinced!
```

---

### 005_update_messages.sql - Message Routing

**Purpose:** Add `party_id` column to `messages` table for tab-based chat routing.

**Changes:**
```sql
ALTER TABLE messages ADD COLUMN party_id VARCHAR NULL;
CREATE INDEX idx_messages_party_id ON messages(party_id);
CREATE INDEX idx_messages_campaign_party ON messages(campaign_id, party_id);
```

**Key Features:**
- **Nullable `party_id`:** Allows existing messages without party association
- **Indexes:** Efficient queries for messages by party or campaign+party
- **Foreign key (soft):** SQLite limitations prevent ALTER TABLE FK, enforced in app code

**Example Queries:**
```sql
-- Get all messages in Story tab
SELECT * FROM messages
WHERE party_id = 'story-party-id'
ORDER BY created_at DESC
LIMIT 50;

-- Get recent IC messages across all parties in campaign
SELECT m.*, p.party_type
FROM messages m
JOIN parties p ON m.party_id = p.id
WHERE m.campaign_id = 'campaign-123'
  AND m.mode = 'IC'
ORDER BY m.created_at DESC
LIMIT 100;

-- Get whisper messages between two characters
SELECT * FROM messages
WHERE party_id IN (
    SELECT id FROM parties
    WHERE party_type = 'whisper'
      AND campaign_id = 'campaign-123'
)
ORDER BY created_at ASC;
```

**Data Migration Note:**
This migration **only adds the column**. Existing messages will have `party_id = NULL`. A separate Python script should migrate historical messages:

```python
# Pseudocode for data migration
def migrate_messages_to_parties():
    for campaign in campaigns:
        story_party = get_or_create_story_party(campaign)

        # Move IC messages to Story tab
        db.execute("""
            UPDATE messages
            SET party_id = ?
            WHERE campaign_id = ? AND mode = 'IC' AND party_id IS NULL
        """, [story_party.id, campaign.id])

        ooc_party = get_or_create_ooc_party(campaign)

        # Move OOC messages to OOC tab
        db.execute("""
            UPDATE messages
            SET party_id = ?
            WHERE campaign_id = ? AND mode = 'OOC' AND party_id IS NULL
        """, [ooc_party.id, campaign.id])
```

---

## Running Migrations

### Option 1: Manual Execution (SQLite)

```bash
# Navigate to project root
cd TBA-App

# Run migrations in order
sqlite3 local.db < backend/migrations/001_add_parties.sql
sqlite3 local.db < backend/migrations/002_add_party_members.sql
sqlite3 local.db < backend/migrations/003_update_characters.sql
sqlite3 local.db < backend/migrations/004_add_abilities.sql
sqlite3 local.db < backend/migrations/005_update_messages.sql
```

### Option 2: Python Migration Script (Recommended)

Create `backend/migrations/run_phase_2d.py`:

```python
import os
from backend.db import engine
from sqlalchemy import text

def run_migrations():
    """Run Phase 2d migrations in order."""
    migration_files = [
        '001_add_parties.sql',
        '002_add_party_members.sql',
        '003_update_characters.sql',
        '004_add_abilities.sql',
        '005_update_messages.sql'
    ]

    migrations_dir = os.path.dirname(__file__)

    with engine.connect() as conn:
        for filename in migration_files:
            filepath = os.path.join(migrations_dir, filename)
            print(f"Running {filename}...")

            with open(filepath, 'r') as f:
                sql = f.read()

            # Split by semicolons and execute each statement
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            for stmt in statements:
                if stmt and not stmt.startswith('--'):
                    conn.execute(text(stmt))

            conn.commit()
            print(f"✓ {filename} completed")

    print("\n✅ All Phase 2d migrations completed successfully!")

if __name__ == '__main__':
    run_migrations()
```

Run it:
```bash
python -m backend.migrations.run_phase_2d
```

### Option 3: PostgreSQL (Production)

```bash
# Connect to database
psql $DATABASE_URL

# Run migrations
\i backend/migrations/001_add_parties.sql
\i backend/migrations/002_add_party_members.sql
\i backend/migrations/003_update_characters.sql
\i backend/migrations/004_add_abilities.sql
\i backend/migrations/005_update_messages.sql
```

---

## Rollback Plan

If you need to undo these migrations:

### 001_add_parties.sql - Rollback
```sql
DROP INDEX IF EXISTS idx_parties_one_ooc_per_campaign;
DROP INDEX IF EXISTS idx_parties_one_story_per_campaign;
DROP INDEX IF EXISTS idx_parties_active;
DROP INDEX IF EXISTS idx_parties_type;
DROP INDEX IF EXISTS idx_parties_campaign_id;
DROP TABLE IF EXISTS parties;
```

### 002_add_party_members.sql - Rollback
```sql
DROP INDEX IF EXISTS idx_party_members_active_unique;
DROP INDEX IF EXISTS idx_party_members_active;
DROP INDEX IF EXISTS idx_party_members_character_id;
DROP INDEX IF EXISTS idx_party_members_party_id;
DROP TABLE IF EXISTS party_members;
```

### 003_update_characters.sql - Rollback
```sql
ALTER TABLE characters DROP COLUMN IF EXISTS notes;
ALTER TABLE characters DROP COLUMN IF EXISTS max_uses_per_encounter;
ALTER TABLE characters DROP COLUMN IF EXISTS current_uses;
ALTER TABLE characters DROP COLUMN IF EXISTS weapon_bonus;
ALTER TABLE characters DROP COLUMN IF EXISTS armor_bonus;
ALTER TABLE characters DROP COLUMN IF EXISTS times_called;
ALTER TABLE characters DROP COLUMN IF EXISTS is_called;
ALTER TABLE characters DROP COLUMN IF EXISTS status;
DROP INDEX IF EXISTS idx_characters_status;
```

### 004_add_abilities.sql - Rollback
```sql
DROP INDEX IF EXISTS idx_abilities_character_macro;
DROP INDEX IF EXISTS idx_abilities_character_slot;
DROP INDEX IF EXISTS idx_abilities_slot;
DROP INDEX IF EXISTS idx_abilities_character_id;
DROP TABLE IF EXISTS abilities;
```

### 005_update_messages.sql - Rollback
```sql
DROP INDEX IF EXISTS idx_messages_created_at;
DROP INDEX IF EXISTS idx_messages_campaign_party;
DROP INDEX IF EXISTS idx_messages_party_id;
ALTER TABLE messages DROP COLUMN IF EXISTS party_id;
```

---

## Testing

After running migrations, verify schema:

```sql
-- Check parties table
SELECT * FROM sqlite_master WHERE type='table' AND name='parties';

-- Check party_members table
SELECT * FROM sqlite_master WHERE type='table' AND name='party_members';

-- Check characters columns
PRAGMA table_info(characters);

-- Check abilities table
SELECT * FROM sqlite_master WHERE type='table' AND name='abilities';

-- Check messages columns
PRAGMA table_info(messages);

-- Verify indexes
SELECT name, sql FROM sqlite_master WHERE type='index';
```

---

## Next Steps

After migrations:

1. **Update SQLAlchemy Models** - Add corresponding model classes in `backend/models.py`
2. **Update API Endpoints** - Create CRUD endpoints for parties, abilities
3. **Update WebSocket Chat** - Modify `routes/chat.py` to route messages by `party_id`
4. **UI Updates** - Build tab system UI in frontend
5. **Data Migration Script** - Migrate existing messages to parties
6. **Character Creation Flow** - Add ability selection during character creation

---

## SQLite vs PostgreSQL Compatibility

These migrations are written for **SQLite compatibility** (used in local development). Key differences:

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| UUID Generation | `lower(hex(randomblob(16)))` | `gen_random_uuid()` |
| Foreign Keys in ALTER | ❌ Not supported | ✅ Supported |
| CHECK Constraints in ALTER | ❌ Not supported | ✅ Supported |
| Comments | ❌ Ignored | ✅ Supported |
| Partial Indexes (WHERE) | ✅ Supported | ✅ Supported |

For production (PostgreSQL), these migrations will work but you can enhance them with:
- Replace `VARCHAR` with `UUID` type
- Add `gen_random_uuid()` for UUIDs
- Add table/column comments
- Add foreign keys in ALTER TABLE statements

---

## Questions?

If you encounter issues:

1. Check SQLite version: `sqlite3 --version` (need 3.8.0+)
2. Verify database file: `ls -lh local.db`
3. Check for syntax errors: Run migrations one at a time
4. Review logs: Check for constraint violations

**Status:** Ready for Phase 2d implementation! 🚀
