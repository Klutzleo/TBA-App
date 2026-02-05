# Database Migration Fix - UUID Type Mismatch

## Problem Summary

Your database migrations were failing due to a type mismatch between `campaigns.id` (UUID) and foreign key columns that reference it (VARCHAR). PostgreSQL cannot create foreign key constraints between columns of different types.

## Root Cause Analysis

### The Type Mismatch Chain

1. **[001_add_parties.sql:12](001_add_parties.sql#L12)** - Creates `parties.campaign_id` as `VARCHAR(36)`
2. **[007_create_campaigns.sql:8](007_create_campaigns.sql#L8)** - Creates `campaigns.id` as `UUID`
3. **[007_create_campaigns.sql:50-51](007_create_campaigns.sql#L50-L51)** - Tries to create FK from VARCHAR to UUID → **FAILS**
4. **[013_add_campaign_management.sql:247](013_add_campaign_management.sql#L247)** - Creates `campaign_memberships.campaign_id` as `VARCHAR(36)`
5. **[019_add_character_campaign_link.sql:5](019_add_character_campaign_link.sql#L5)** - Creates `characters.campaign_id` as `VARCHAR`

### Why Previous Fix Attempts Failed

- **006_z_fix_parties_campaign_id.sql** - Only cleared data but didn't change the type
- **006_zz_convert_campaigns_to_uuid.sql** - Dropped campaigns table but `parties.campaign_id` was still VARCHAR
- **020_force_campaigns_uuid.sql** - Recreated campaigns with UUID but line 35-36 still tried to add FK from VARCHAR column
- **021_fix_parties_campaign_id_uuid.sql** - Tried to convert parties.campaign_id but would fail if any non-UUID values existed
- **campaign_overview view** - Blocked ALTER TABLE operations

## The Solution

**New Migration: [022_consolidate_uuid_fix.sql](022_consolidate_uuid_fix.sql)**

This consolidated migration properly handles the UUID conversion:

1. ✅ **Drops blocking views** - Removes `campaign_overview` view first
2. ✅ **Ensures campaigns table** - Creates/recreates `campaigns` table with UUID id
3. ✅ **Converts FK columns** - Changes all foreign key columns to UUID:
   - `parties.campaign_id`: VARCHAR → UUID
   - `campaign_memberships.campaign_id`: VARCHAR → UUID
   - `characters.campaign_id`: UUID (if needed)
4. ✅ **Handles invalid data** - Safely converts or nullifies invalid UUID values
5. ✅ **Creates FK constraints** - Properly links all foreign keys
6. ✅ **Recreates triggers** - Restores campaign channel creation triggers
7. ✅ **Recreates views** - Rebuilds `campaign_overview` view with correct schema

### Key Features

- **Idempotent** - Safe to run multiple times
- **Data-safe** - Only nullifies invalid UUIDs, doesn't drop valid data
- **Complete** - Handles all tables that reference campaigns
- **Properly ordered** - Executes steps in the correct dependency order

## How to Use

### Option 1: Run Migrations Normally

The new migration is already added to `run_phase_2d.py`, so just run:

```bash
python backend/migrations/run_phase_2d.py
```

### Option 2: Nuclear Reset (Clean Slate)

If you want to completely reset the database:

```bash
python backend/migrations/run_phase_2d.py --nuclear
```

This will:
1. Drop ALL tables
2. Recreate everything from scratch
3. Run all migrations in order including the new fix

### Option 3: Manual SQL Execution

You can also run the migration manually:

```bash
psql -d your_database < backend/migrations/022_consolidate_uuid_fix.sql
```

## Migration Order

The migrations now run in this order:

```
001-021: Original migrations (some will partially fail, which is OK)
022: Consolidated UUID fix (fixes everything)
```

## What Gets Fixed

After running migration 022:

| Table | Column | Old Type | New Type | FK Status |
|-------|--------|----------|----------|-----------|
| campaigns | id | UUID | UUID | Primary Key |
| parties | campaign_id | VARCHAR(36) | UUID | ✅ FK to campaigns(id) |
| campaign_memberships | campaign_id | VARCHAR(36) | UUID | ✅ FK to campaigns(id) |
| characters | campaign_id | VARCHAR | UUID | ✅ FK to campaigns(id) |

## Recommended Cleanup (Optional)

After verifying the fix works, you can optionally remove these now-redundant migration files:

- `006_z_fix_parties_campaign_id.sql` - Superseded by 022
- `006_zz_convert_campaigns_to_uuid.sql` - Superseded by 022
- `020_force_campaigns_uuid.sql` - Superseded by 022
- `021_fix_parties_campaign_id_uuid.sql` - Superseded by 022

**Note:** Don't delete these yet! Wait until you've successfully run the migrations in production.

## Verification

After running migrations, verify the fix:

```sql
-- Check campaigns table
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'campaigns' AND column_name = 'id';
-- Should show: uuid

-- Check parties foreign key
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'parties' AND column_name = 'campaign_id';
-- Should show: uuid

-- Check constraints
SELECT constraint_name, table_name
FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY'
AND table_name IN ('parties', 'campaign_memberships', 'characters')
AND constraint_name LIKE '%campaign%';
-- Should show all three FK constraints exist
```

## Troubleshooting

### If migration 022 fails:

1. Check the error message in the logs
2. The migration includes exception handling - it will tell you what failed
3. You can run it again - it's idempotent

### If you have existing data:

- The migration safely handles existing data
- Invalid UUID values in campaign_id columns will be set to NULL
- Valid UUID strings will be converted to UUID type
- Since this is early development, data loss on invalid IDs is acceptable

### If foreign keys still fail:

Run this diagnostic query:

```sql
-- Check for orphaned campaign_id references
SELECT 'parties' as table_name, campaign_id
FROM parties
WHERE campaign_id IS NOT NULL
AND campaign_id NOT IN (SELECT id FROM campaigns)
UNION ALL
SELECT 'campaign_memberships', campaign_id::text
FROM campaign_memberships
WHERE campaign_id IS NOT NULL
AND campaign_id NOT IN (SELECT id FROM campaigns);
```

If you find orphaned references, run:

```sql
-- Clean up orphaned references
UPDATE parties SET campaign_id = NULL
WHERE campaign_id NOT IN (SELECT id FROM campaigns);

DELETE FROM campaign_memberships
WHERE campaign_id NOT IN (SELECT id FROM campaigns);
```

## Contact

If you encounter issues not covered here, check the migration logs for detailed error messages.
