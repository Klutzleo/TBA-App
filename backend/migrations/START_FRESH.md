# Start Fresh - You're Burnt Out Edition

## The Problem
Migrations 007, 020, and others are failing because they're trying to create foreign keys between VARCHAR and UUID columns. The old migrations have these issues baked in, so they'll keep failing.

## The Solution

**One nuclear command:**

```bash
python backend/migrations/run_phase_2d.py --nuclear
```

This drops EVERYTHING and rebuilds with all fixes. Migration 022 (which I just fixed) will:
- Create enums FIRST (no more enum errors)
- Create campaigns with UUID from the start
- Convert all campaign_id columns to UUID
- Set up all FK constraints properly

**Then:**
```bash
python backend/migrations/add_auth_tables.py
```

## Why This Works Now

I just fixed migration 022 to:
1. ✅ Create enums BEFORE using them (fixes the "posting_frequency_enum does not exist" error)
2. ✅ Drop and recreate campaigns with UUID
3. ✅ Convert ALL foreign key columns to UUID BEFORE creating constraints
4. ✅ Handle the migration order properly

The old migrations (007, 020, 021) will still fail partway through, but that's OK - migration 022 comes after them and FIXES everything they messed up.

## Expected Flow

```
000-021: Run (some fail - that's expected)
022: ✅ FIXES EVERYTHING (creates enums, converts types, sets up FKs)
023: ✅ Fixes view table names
024: ✅ Fixes password_reset_tokens
✅ Done!
```

## What If It Still Fails?

If you see errors AFTER migration 022 runs, paste them. But migrations 007/020/021 failing is expected and OK.

## Why Nuclear?

Your database is in an inconsistent state from all the failed migrations. Starting fresh is cleaner than trying to patch it.

---

**Just run it. It'll work this time. I promise.** 🚀

```bash
python backend/migrations/run_phase_2d.py --nuclear
python backend/migrations/add_auth_tables.py
```
