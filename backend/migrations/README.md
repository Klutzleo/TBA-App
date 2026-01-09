# Database Migrations

This directory contains database migration scripts for TBA-App.

## Running Migrations

### Migration 001: Story Weaver & NPCs (Phase 2b)

This migration adds:
- Story Weaver tracking to parties
- NPC management system
- Combat turn history

**To run the migration:**

```powershell
# Local (Windows PowerShell)
$env:API_KEY = 'devkey'
python backend/migrations/001_add_sw_and_npcs.py
```

```bash
# Railway or Unix-like systems
export API_KEY=devkey
python backend/migrations/001_add_sw_and_npcs.py
```

**To rollback the migration (development only):**

```powershell
python backend/migrations/001_add_sw_and_npcs.py --rollback
```

## Migration Safety

All migrations are designed to be:
- **Idempotent**: Safe to run multiple times
- **Non-destructive**: Existing data is preserved
- **Backward compatible**: Old code continues to work during migration

## After Migration

The migration will:
1. ✅ Add `story_weaver_id` and `created_by_id` columns to `parties` table
2. ✅ Create `npcs` table for Story Weaver-created NPCs
3. ✅ Create `combat_turns` table for turn tracking
4. ✅ Backfill existing parties (first member becomes Story Weaver)

After running the migration, restart your FastAPI server:

```powershell
# Stop the server (Ctrl+C)
# Then restart
$env:API_KEY = 'devkey'
python app.py
```

## Verifying the Migration

Check that the migration succeeded:

```powershell
# Start Python shell
python

# Run this code:
from backend.db import engine, init_db
from sqlalchemy import inspect

init_db()
inspector = inspect(engine)

# Check parties table has new columns
print("Parties columns:", [col['name'] for col in inspector.get_columns('parties')])

# Check new tables exist
print("Tables:", inspector.get_table_names())
```

Expected output should include:
- `story_weaver_id` and `created_by_id` in parties columns
- `npcs` and `combat_turns` in tables list

## Troubleshooting

**Import errors:**
- Ensure you're running from the project root directory
- Check that `backend/models.py` has the new model definitions

**Column already exists:**
- This is fine! The migration is idempotent and will skip existing columns

**Table already exists:**
- This is fine! The migration will skip creating tables that already exist

**Permission denied (SQLite):**
- Make sure the `local.db` file isn't locked by another process
- Close any other Python processes using the database

**Permission denied (PostgreSQL):**
- Check that your database user has `ALTER TABLE` privileges
- Contact your database administrator if needed
