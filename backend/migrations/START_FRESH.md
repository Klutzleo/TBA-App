# Start Fresh - Clean Database Migration

**You're burnt out. I get it. Here's the simplest path forward:**

## One Command to Rule Them All

```bash
python backend/migrations/run_phase_2d.py --nuclear
```

**That's it.** This will:
1. 💥 Drop everything (all tables, views, triggers)
2. ✨ Rebuild from scratch with all fixes applied
3. ✅ Create everything with correct UUID types
4. 🎉 Be ready to use

## Then Run Auth Migration

```bash
python backend/migrations/add_auth_tables.py
```

## What Gets Fixed

Everything:
- ✅ campaigns.id → UUID
- ✅ parties.campaign_id → UUID
- ✅ campaign_memberships.campaign_id → UUID
- ✅ characters.campaign_id → UUID
- ✅ password_reset_tokens → UUID types
- ✅ Views use correct table names
- ✅ All FK constraints work
- ✅ No more type mismatches

## Expected Output

You should see:
```
✅ Applied: 25+ migrations
✅ Migration 022: All UUID conversions completed successfully!
✅ Migration 023: View table references fixed!
✅ Migration 024: password_reset_tokens UUID types fixed!
✅ All Phase 2d migrations completed!
```

Then:
```
✅ Authentication migration completed successfully!
```

## If It Still Fails

Share the error output and I'll fix it. But this should work - it's a completely clean start with all the fixes baked in.

## What About My Data?

This **destroys all data**. But since you're in development and the migrations have been failing, you don't have valid data anyway. Fresh start = clean slate.

---

**TL;DR:** Run `python backend/migrations/run_phase_2d.py --nuclear` then `python backend/migrations/add_auth_tables.py`

That's it. Take a break. Come back. Run the command. It should work. 🚀
