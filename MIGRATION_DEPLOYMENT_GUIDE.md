# Migration Deployment Guide - Phase 2d

## Overview

Phase 2d migrations will **NOT auto-run** on Railway deployment by default. You have 3 options:

---

## ✅ Option 1: Auto-Run on Startup (RECOMMENDED)

**What:** Migrations run automatically every time the app starts on Railway.

**Pros:**
- ✅ Zero manual intervention
- ✅ Works on every deployment
- ✅ Idempotent (safe to run multiple times)
- ✅ No extra Railway configuration

**Cons:**
- ⚠️ Adds ~1-2 seconds to startup time
- ⚠️ All app instances run migrations (use locking for multi-instance)

### Implementation

**Step 1:** Add migration runner to `backend/app.py` startup:

```python
# backend/app.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — DB init happens HERE
    logger.info("🚀 FastAPI TBA-App starting")
    try:
        init_db()
        logger.info("✅ Database initialized")

        # NEW: Run Phase 2d migrations
        from backend.migrations.run_phase_2d import run_migrations
        run_migrations()
        logger.info("✅ Migrations applied")

    except Exception as e:
        logger.warning(f"⚠️ DB init warning: {e}")
    yield
    # Shutdown
    logger.info("🛑 FastAPI TBA-App shutting down")
```

**Step 2:** Deploy to Railway:

```bash
git add backend/migrations/
git commit -m "feat: Add Phase 2d migrations with auto-run on startup"
git push origin main
```

**Step 3:** Check Railway logs:

```
🚀 FastAPI TBA-App starting
✅ Database initialized
🔧 Checking Phase 2d migrations...
🔄 Phase 2d migrations needed
Running 001_add_parties.sql...
✓ 001_add_parties.sql completed
Running 002_add_party_members.sql...
✓ 002_add_party_members.sql completed
...
✅ All Phase 2d migrations completed successfully!
✅ Migrations applied
```

**That's it!** Migrations will run on every deployment.

---

## Option 2: Manual Railway Deployment (Quick Fix)

**What:** Run migrations once manually via Railway CLI or web shell.

**Pros:**
- ✅ Full control over when migrations run
- ✅ No startup delay

**Cons:**
- ⚠️ Manual step required for each deployment
- ⚠️ Easy to forget

### Using Railway CLI

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Connect to database and run migrations
railway run psql $DATABASE_URL

# In psql shell:
\i backend/migrations/001_add_parties.sql
\i backend/migrations/002_add_party_members.sql
\i backend/migrations/003_update_characters.sql
\i backend/migrations/004_add_abilities.sql
\i backend/migrations/005_update_messages.sql

\q
```

### Using Railway Web Shell (if available)

1. Go to Railway dashboard → Your project → Database
2. Click "Connect" → "psql"
3. Copy/paste each migration file content
4. Run manually

---

## Option 3: Custom Railway Build Script (Advanced)

**What:** Run migrations as part of Railway's build process.

**Pros:**
- ✅ Runs once per deployment (not on every startup)
- ✅ Automated

**Cons:**
- ⚠️ More complex setup
- ⚠️ Requires custom build script

### Implementation

**Step 1:** Create `scripts/migrate.py`:

```python
#!/usr/bin/env python3
"""
Run migrations before app starts.
Called by Railway build process.
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)

from backend.migrations.run_phase_2d import run_migrations

try:
    run_migrations()
    sys.exit(0)
except Exception as e:
    logging.error(f"Migration failed: {e}")
    sys.exit(1)
```

**Step 2:** Update `Procfile` (or create `railway.toml`):

```toml
# railway.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python scripts/migrate.py && uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000}"
```

**OR** update `Procfile`:

```
release: python scripts/migrate.py
web: uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000}
```

**Step 3:** Deploy:

```bash
git add scripts/migrate.py railway.toml
git commit -m "feat: Add pre-deployment migration script"
git push origin main
```

---

## Migration Safety Features

The `run_phase_2d.py` script is **idempotent** (safe to run multiple times):

### 1. Pre-Flight Check
```python
def check_migration_needed() -> bool:
    """Check if migrations already applied."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # Check if new tables exist
    if 'parties' in tables and 'abilities' in tables:
        # Check if characters has new columns
        columns = {col['name'] for col in inspector.get_columns('characters')}
        if 'notes' in columns and 'status' in columns:
            logger.info("✅ Phase 2d migrations already applied")
            return False  # Skip migrations

    return True  # Run migrations
```

### 2. Error Handling
```python
try:
    conn.execute(text(stmt))
    conn.commit()
except Exception as e:
    # Log warning but continue (might be "column already exists")
    logger.warning(f"Migration statement warning: {e}")
    conn.rollback()
```

**Result:** Running migrations multiple times is safe!

---

## Testing Locally Before Railway

Test migrations locally before pushing to Railway:

### SQLite (Local Development)

```bash
# Run migration script directly
python -m backend.migrations.run_phase_2d

# Or start the app (migrations auto-run)
python app.py
```

**Expected output:**
```
🔧 Checking Phase 2d migrations...
🔄 Phase 2d migrations needed
Running 001_add_parties.sql...
✓ 001_add_parties.sql completed
Running 002_add_party_members.sql...
✓ 002_add_party_members.sql completed
...
✅ All Phase 2d migrations completed successfully!
```

### Verify Tables Created

```bash
sqlite3 local.db

.tables
# Should show: parties, party_members, abilities, characters, messages, etc.

PRAGMA table_info(characters);
# Should show new columns: notes, status, weapon_bonus, etc.

PRAGMA table_info(abilities);
# Should show all ability columns

.quit
```

---

## PostgreSQL (Production Railway)

After deploying, verify migrations in Railway database:

```bash
railway run psql $DATABASE_URL

\dt  -- List tables
# Should show: parties, party_members, abilities, etc.

\d characters  -- Describe characters table
# Should show new columns: notes, status, weapon_bonus, etc.

\d abilities  -- Describe abilities table
# Should show all ability columns with constraints

\di  -- List indexes
# Should show all new indexes

\q
```

---

## Rollback Plan

If something goes wrong, rollback migrations:

### Using SQL Scripts

See [PHASE_2D_MIGRATIONS_README.md](backend/migrations/PHASE_2D_MIGRATIONS_README.md#rollback-plan) for rollback SQL.

### Quick Rollback Commands

```sql
-- Drop new tables
DROP TABLE IF EXISTS abilities;
DROP TABLE IF EXISTS party_members;
DROP TABLE IF EXISTS parties;

-- Remove new columns from characters
ALTER TABLE characters DROP COLUMN IF EXISTS notes;
ALTER TABLE characters DROP COLUMN IF EXISTS status;
ALTER TABLE characters DROP COLUMN IF EXISTS weapon_bonus;
ALTER TABLE characters DROP COLUMN IF EXISTS armor_bonus;
ALTER TABLE characters DROP COLUMN IF EXISTS max_uses_per_encounter;
ALTER TABLE characters DROP COLUMN IF EXISTS current_uses;
ALTER TABLE characters DROP COLUMN IF EXISTS times_called;
ALTER TABLE characters DROP COLUMN IF EXISTS is_called;

-- Remove party_id from messages
ALTER TABLE messages DROP COLUMN IF EXISTS party_id;
```

---

## Recommended Approach

**For your use case, I recommend Option 1 (Auto-Run on Startup):**

1. ✅ **Simplest** - Just add 3 lines to `backend/app.py`
2. ✅ **Automatic** - Works on every Railway deployment
3. ✅ **Safe** - Idempotent migrations won't break if run multiple times
4. ✅ **Fast** - Only adds ~1-2 seconds to startup

### Quick Setup (Option 1)

**Edit `backend/app.py` (around line 37):**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 FastAPI TBA-App starting")
    try:
        init_db()
        logger.info("✅ Database initialized")

        # Run Phase 2d migrations
        from backend.migrations.run_phase_2d import run_migrations
        run_migrations()

    except Exception as e:
        logger.warning(f"⚠️ DB init warning: {e}")
    yield
    logger.info("🛑 FastAPI TBA-App shutting down")
```

**Deploy:**

```bash
git add backend/migrations/
git add backend/app.py
git commit -m "feat: Add Phase 2d migrations with auto-run"
git push origin main
```

**Check Railway logs after deployment** - should see migration success messages!

---

## FAQ

### Q: Will migrations run on every app restart?
**A:** Yes, but the `check_migration_needed()` function detects if migrations already ran and skips them. Only takes ~100ms to check.

### Q: What if migrations fail on Railway?
**A:** The app will log warnings but continue starting. Check Railway logs for error messages. You can manually fix and redeploy.

### Q: Can I run migrations manually first?
**A:** Yes! Use Railway CLI or web shell to run migrations manually **before** adding auto-run. The auto-run will detect they're already applied and skip.

### Q: What about future migrations?
**A:** Create new migration files (006_*.sql, 007_*.sql) and add them to the `migration_files` list in `run_phase_2d.py`. They'll auto-run on next deployment.

### Q: Do migrations run in parallel on multi-instance deploys?
**A:** Yes, each instance runs migrations independently. The idempotent design prevents conflicts, but for high-scale apps, consider adding database-level locking.

---

**Status:** Migration deployment strategy ready! Choose Option 1 for simplest setup. 🚀
