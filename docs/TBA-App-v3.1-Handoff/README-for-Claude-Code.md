# Handoff: update TBA-App to rules v3.1 (final v3.1, Nov 16)

You are working in the TBA-App repo. `main` is production (tba-rpg.com), so work on a branch.

## What's in this bundle
- `rules/adult/core-rules.md` and `rules/kids/core-rules.md`: the rules. Adult is the source of truth. Kids has the same numbers with different terms. The Leveling Table is at the end of the Leveling chapter.
- `rules/*/story-weaver-guide.md`: NPC building, Calling procedure, buff/debuff examples, common effects.
- `content/`: archetypes and character sheets (Adult and Kids), plus the six quick-start adventures. Each adventure has an "APP PLAY VARIANT" box describing how it plays turn-based in the app.
- `notes/decisions.md`: every decision and why, including what is parked for v3.2. Read it before changing anything.
- `notes/app-audit.md`: a first-pass gap list made by reading the code on Nov 10 (read only, app not run). Starting point, not the answer.
- `notes/audit-nov16.md`: the rules audit; all items resolved.

## What to do
1. Do your own audit of the repo against the Core. Compare against the audit, and say where you disagree.
2. Replace the repo's `Rulebook.md` and `LevelingTable.md` with v3.1 (the table now lives inside the core rules file).
3. Write a file-by-file plan before changing code. Include tests that will break (for example, DP expectations in `tests/test_characters.py`).
4. Build on a branch with tests and a before/after report.

## Rules that changed most (check these first)
- DP is 8 at level 1, +2 per level. Uses per encounter = level + 2, one shared pool.
- Buff and debuff table: 1d6 +/-1, 1d8 +/-2, 1d10 +/-2, 1d12 +/-3, 2d6 +/-3, 2d8 +/-4. Lasts 2 rounds: you get one action with it on your next turn, and it ends at the start of your turn after that. One buff and one debuff per stat per target; a new one replaces the old; both apply to the roll. Casting takes your turn.
- Healing rolls spell die + stat + Edge, like any spell (changed Nov 10), once per encounter per target.
- Calling: a tie is Marked (survive), not death.
- BAP goes on one roll of an action; on a multi-die weapon the player says which die.
- Tethers have their own **+1 to +4** scale (not +5); only the strongest bonus and strongest penalty count, netted; a Tether is its own layer on top of buffs and debuffs, and can add to or take from a Calling roll. Grief is -1 to -3.
- **Combos (changed Nov 10):** every Combo costs **1 use per character** (Triple Combo too). A Combo with no attack: the heal adds the healer's BAP, and a buff or debuff counts one step higher on the buff table (+4 max). Once per encounter, either partner at 0 DP cancels it.
- **Summons (changed Nov 10):** calling one is free and instant (no action, acts right after your turn). Each round it acts costs 1 use, and that is its upkeep (no DP drain); out of uses, it fades. It rolls with the stat you use for that spell or technique, not always Intellect. No heals on summons (hits, not DP).
- **Area attacks:** each target defends with the same stat the attack used.
- **Damage Effects (poison, burning, bleeding, etc.):** damage over time, not a buff or debuff. Cast like a debuff; if it lands, the target takes the spell die once at the start of their next turn and can resist for half. They can take someone to -10 and The Calling.
- **BAP effect:** a BAP moment (SW awards the BAP) can also give a +1 or -1 for 1 round, SW picks the stat.
- **Item bonuses:** no cap.
- **Changed Nov 16 (final pass):**
  - Combos: if both effects hit the same stat, the stronger one takes over (they don't stack).
  - Marked by Death (Kids: Battle Scarred): up to 4, the 5th is out. A scar or fear becomes a new Tether; a limitation just stays with you. The old "lose 1 max DP" is gone.
  - Healing is once per person per encounter. Character sheets now have a "Healed this encounter" box; the app should track it.
  - "Called count" is the tracked number of times a character has been Called.
  - BAP effect lasts until the start of your next turn.
  - Vehicles: Captain/Pilot add to attack OR defense; unmanned stations don't function, except defense.
  - Kids wording: The Challenge, Battle Scarred, "out of the adventure" (replaces "knocked out for good"). Kids archetypes and adventures carry no borrowed names or quotes.
- Allies use their own table (half DP). Ascension (levels 11 to 15) is next.

## Decide with Jason before building
- Existing characters and campaigns: do the new numbers apply to new characters only, or migrate everyone?
- Kids terminology mode: add one, or leave the app on the Adult terms?
