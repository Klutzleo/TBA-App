#!/usr/bin/env python3
"""
One-time migration of existing characters to the rules v3.1 numbers.

  python scripts/migrate_rules_v31.py            dry run (default): prints what would change, writes nothing
  python scripts/migrate_rules_v31.py --apply    does it, saving every old value first
  python scripts/migrate_rules_v31.py --undo     puts every migrated character back exactly as it was

What it changes (everyone: PCs, NPCs, Allies; not summons or objects):
  - max DP becomes the v3.1 table value for the character's level (8 at level 1, +2 per level).
  - current DP keeps the same PERCENTAGE of max (not the raw number, not a full heal). A living character never
    rounds down to 0 (minimum 1), current DP never exceeds the new max, and anyone at 0 DP or below, or in The
    Calling, is left exactly as they are.
  - uses per encounter become level + 2; every ability's max and remaining uses are set to that (a one-time
    refill; the shared pool arrives in a later phase).
  - a weapon die that is not legal at the character's level (for example the removed 3d4/4d4/5d4/4d6, or an
    illegal 4d10) is replaced by the first legal option for that level (a single die); legal dice are untouched.

Safety:
  - Refuses to apply while any encounter is active (initiative rows carry copies of DP), unless --force.
  - Idempotent: a character that already has a backup row is skipped, so running --apply twice is harmless.
  - The backup tables are created by this script (CREATE TABLE IF NOT EXISTS), one row per character and ability.
  - Uses DATABASE_URL like the app does. Point it at prod only with Jason's explicit go-ahead.
"""
import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from backend.leveling import MAX_LEVEL, level_stats, uses_for_level, weapon_options, ally_stats, ally_weapon_options  # noqa: E402

CHAR_BACKUP = "rules_v31_migration_backup"
ABILITY_BACKUP = "rules_v31_migration_ability_backup"


def ensure_backup_tables(db):
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {CHAR_BACKUP} (
        character_id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(255), level INTEGER,
        old_max_dp INTEGER, old_dp INTEGER, old_max_uses INTEGER, old_current_uses INTEGER,
        new_max_dp INTEGER, new_dp INTEGER, old_attack_style VARCHAR(20), new_attack_style VARCHAR(20),
        migrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {ABILITY_BACKUP} (
        ability_id VARCHAR(36) PRIMARY KEY, character_id VARCHAR(36),
        old_max_uses INTEGER, old_uses_remaining INTEGER,
        migrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
    db.commit()


def new_current_dp(dp, old_max, new_max, in_calling=False):
    """Same percentage of max. Untouched at 0 DP or below or in The Calling; min 1 if alive; never above the new max."""
    dp = dp if dp is not None else 0
    if dp <= 0 or in_calling:
        return dp
    if not old_max or old_max <= 0:
        return new_max
    scaled = int(dp * new_max / old_max + 0.5)
    return max(1, min(new_max, scaled))


def plan(db):
    """Rows to migrate (nothing is written). Each is a dict with old and new values."""
    from backend.models import Character
    from sqlalchemy import inspect
    # Strictly read-only: the backup tables are only created by --apply / --undo, never by a dry run.
    done = set()
    if inspect(db.get_bind()).has_table(CHAR_BACKUP):
        done = {r[0] for r in db.execute(text(f"SELECT character_id FROM {CHAR_BACKUP}"))}
    rows, skipped = [], []
    for c in db.query(Character).order_by(Character.name).all():
        if c.is_summon or c.is_object:
            skipped.append((c.name, "summon/object"))
            continue
        if str(c.id) in done:
            skipped.append((c.name, "already migrated"))
            continue
        level = c.level or 1
        if not 1 <= level <= MAX_LEVEL:
            skipped.append((c.name, f"level {level} outside 1-{MAX_LEVEL}"))
            continue
        new_max = (ally_stats if c.is_ally else level_stats)(level)["max_dp"]
        rows.append({
            "char": c, "name": c.name, "level": level, "npc": bool(c.is_npc),
            "old_max_dp": c.max_dp, "old_dp": c.dp, "new_max_dp": new_max,
            "new_dp": new_current_dp(c.dp, c.max_dp, new_max, bool(c.in_calling)),
            "old_max_uses": c.max_uses_per_encounter, "old_current_uses": c.current_uses,
            "new_uses": uses_for_level(level),
            "old_attack_style": c.attack_style,
            "new_attack_style": c.attack_style if c.attack_style in (ally_weapon_options if c.is_ally else weapon_options)(level) else (ally_weapon_options if c.is_ally else weapon_options)(level)[0],
        })
    return rows, skipped


def active_encounters(db):
    from backend.models import Encounter
    return db.query(Encounter).filter(Encounter.is_active == True).count()  # noqa: E712


def _swap_weapon_die(c, old, new):
    """Set the attack style, and keep the weapon's own die in step when it carried the same value."""
    if old == new:
        return
    c.attack_style = new
    w = c.weapon
    if isinstance(w, dict) and w.get("die") == old:
        c.weapon = {**w, "die": new}


def apply(db):
    from backend.models import Ability
    ensure_backup_tables(db)
    rows, _ = plan(db)
    for r in rows:
        c = r["char"]
        db.execute(text(f"""INSERT INTO {CHAR_BACKUP}
            (character_id, name, level, old_max_dp, old_dp, old_max_uses, old_current_uses, new_max_dp, new_dp,
             old_attack_style, new_attack_style)
            VALUES (:id, :name, :level, :omd, :od, :omu, :ocu, :nmd, :nd, :oas, :nas)"""),
            dict(id=str(c.id), name=c.name, level=r["level"], omd=r["old_max_dp"], od=r["old_dp"],
                 omu=r["old_max_uses"], ocu=r["old_current_uses"], nmd=r["new_max_dp"], nd=r["new_dp"],
                 oas=r["old_attack_style"], nas=r["new_attack_style"]))
        for ab in db.query(Ability).filter(Ability.character_id == c.id).all():
            db.execute(text(f"""INSERT INTO {ABILITY_BACKUP}
                (ability_id, character_id, old_max_uses, old_uses_remaining) VALUES (:a, :c, :m, :r)"""),
                dict(a=str(ab.id), c=str(c.id), m=ab.max_uses, r=ab.uses_remaining))
            ab.max_uses = r["new_uses"]
            ab.uses_remaining = r["new_uses"]
        c.max_dp = r["new_max_dp"]
        c.dp = r["new_dp"]
        c.max_uses_per_encounter = r["new_uses"]
        c.current_uses = r["new_uses"]
        _swap_weapon_die(c, r["old_attack_style"], r["new_attack_style"])
    db.commit()
    return len(rows)


def undo(db):
    from backend.models import Ability, Character
    ensure_backup_tables(db)
    n = 0
    for (cid, omd, od, omu, ocu, oas, nas) in db.execute(text(
            f"SELECT character_id, old_max_dp, old_dp, old_max_uses, old_current_uses, old_attack_style, "
            f"new_attack_style FROM {CHAR_BACKUP}")).fetchall():
        c = db.query(Character).filter(Character.id == uuid.UUID(str(cid))).first()
        if c:
            c.max_dp, c.dp, c.max_uses_per_encounter, c.current_uses = omd, od, omu, ocu
            _swap_weapon_die(c, nas, oas)
            n += 1
    for (aid, om, orr) in db.execute(text(
            f"SELECT ability_id, old_max_uses, old_uses_remaining FROM {ABILITY_BACKUP}")).fetchall():
        ab = db.query(Ability).filter(Ability.id == uuid.UUID(str(aid))).first()
        if ab:
            ab.max_uses, ab.uses_remaining = om, orr
    db.execute(text(f"DELETE FROM {ABILITY_BACKUP}"))
    db.execute(text(f"DELETE FROM {CHAR_BACKUP}"))
    db.commit()
    return n


def _print_plan(rows, skipped):
    print(f"{'name':24} {'lvl':>3} {'kind':>4}  {'DP now':>9} -> {'DP new':>9}   {'uses':>9}  weapon")
    for r in rows:
        kind = "NPC" if r["npc"] else "PC"
        print(f"{(r['name'] or '')[:24]:24} {r['level']:>3} {kind:>4}  "
              f"{str(r['old_dp'])+'/'+str(r['old_max_dp']):>9} -> {str(r['new_dp'])+'/'+str(r['new_max_dp']):>9}   "
              f"{str(r['old_max_uses'])+'->'+str(r['new_uses']):>9}  "
              + (f"{r['old_attack_style']} -> {r['new_attack_style']}" if r['old_attack_style'] != r['new_attack_style'] else "ok"))
    print(f"\n{len(rows)} character(s) to migrate, {len(skipped)} skipped.")
    for name, why in skipped:
        print(f"  skipped {name}: {why}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the changes (default is a dry run)")
    ap.add_argument("--undo", action="store_true", help="restore every migrated character from the backup")
    ap.add_argument("--force", action="store_true", help="apply even if an encounter is active (not recommended)")
    args = ap.parse_args(argv)

    from backend.db import SessionLocal
    db = SessionLocal()
    try:
        if args.undo:
            print(f"Restored {undo(db)} character(s) from the backup.")
            return 0
        rows, skipped = plan(db)
        _print_plan(rows, skipped)
        if not args.apply:
            print("\nDry run: nothing was written. Re-run with --apply to migrate.")
            return 0
        live = active_encounters(db)
        if live and not args.force:
            print(f"\nRefusing: {live} encounter(s) are active. End them first, or use --force.")
            return 2
        print(f"\nMigrated {apply(db)} character(s). Undo with --undo.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
