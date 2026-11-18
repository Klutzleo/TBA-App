# TBA-App: v3.1 audit and plan (Nov 16, 2026)

Branch: `rules-v3.1` (local, nothing pushed). Source of truth: `docs/TBA-App-v3.1-Handoff/rules/adult/core-rules.md`
(the final Nov 16 text, newer than `docs/tba_rules-3.1.md` from Oct 9). Kids mode is out of scope for now.
This is an audit and a plan only. No app code has been changed.

Baseline: `pytest tests/` = 212 passed, 5 skipped (after pinning starlette to 0.38.6 locally; the machine had
starlette 1.10, which breaks the pinned FastAPI 0.115 and made 100+ tests error. Production builds from
`requirements.txt`, so it was never affected).

## 1. Where I agree and disagree with the Nov 9 gap report

I read the code paths below myself. Rows 9 (Allies) and 10 (Tethers) in the report I have not re-verified yet.

| Report row | Verdict | What I found |
|:--|:--|:--|
| 1 DP | Agree, and it is in more places | DP lives in 6 copies: `backend/character_utils.py` `DP_BY_LEVEL`; `routes/character_fastapi.py` `LEVEL_STATS` (~2795, also holds uses and defense die); `static/game.html` `PC_DP_BY_LEVEL`, `ALLY_DP_BY_LEVEL`, `PC_USES_BY_LEVEL`; `static/create-character.html`; `static/create-ally.html`. |
| 2 Uses | **Bigger than reported** | Uses are **per ability**, not a pool. Every ability gets its own `max_uses` equal to the whole level total, and a cast decrements only that ability (`campaign_websocket.py` ~2150). `Character.current_uses` is not used by casting. v3.1 says one shared pool (level + 2). This is a structural change. |
| 3 Weapon dice | Agree | `get_available_attack_styles` and `NPC_WEAPON_OPTIONS_BY_LEVEL` in game.html both offer 3d4/4d4/5d4/4d6. |
| 4 Buff table | Agree | `BUFF_DEBUFF_TABLE` is used in 5 places, not 1: ability buff, ability debuff, and three SW-applied effect paths (~3435, ~3498, ~3739: Boost, Stat Check, hazard-style effects). All need the new table. |
| 5 Duration | Agree, with a wrinkle | Effects tick down at the end of the **affected character's own turn**, not per round (~5063). v3.1 says "2 rounds: the cast round and the next". |
| 6 Stacking | Agree | No replace-on-same-stat; effects just accumulate. |
| 7 Healing | Agree | Die + stat only (no Edge), no once-per-encounter record exists anywhere, healing a character at negative DP just adds to the negative number (v3.1: reset to 0 first, then add). |
| 8 Calling | **Wider than reported** | Tie kills (`margin >= 1`). Also: `times_called` goes up on **every** Calling including clean returns, and entering the Calling a 5th time is instant permadeath with no roll (3 sites: ~1420, ~1918, ~3354, plus `resolve_the_calling`). v3.1: only a Mark counts, and the 5th Mark kills. Ascension difficulty bonus (+1 at 13-14, +2 at 15) missing. |
| 9 Allies | Not re-verified | The app's Ally DP table is 5 to 27 and its weapon options are single dice; v3.1 is 4 to 13. |
| 10 Tethers | Not re-verified | `routes/bonds.py` grief weight clamp is -5..-1; v3.1 is -1..-3. |
| 11 Ascension | Agree | Hard cap 10 in `calculate_level_stats`, schemas, and several UI spots. Triple Combo gate is `== 10` (~5766, should be 11+). |
| 12 Rule text | Agree | `Rulebook.md`, `LevelingTable.md` are v3.0. |
| 13 Combos | **Different from the report** | A Combo in the app only **rolls two totals and adds BAP** (`_resolve_combo`). It does not pick a target, roll a defense, apply damage, or apply a buff/heal; the SW narrates the result. Cost is 2 uses per character for both Combo and Triple (the report says 3 for Triple; the code says 2). No +2 Triple bonus. The "buff counts one step up" and "heal adds BAP" rules have nothing to attach to unless Combos become automated. |
| Not in report | **Summons changed Nov 10** | Report says summons match. They no longer do. v3.1: calling a summon is free and instant; each round it acts costs 1 use and is its upkeep (no DP drain); it fades when the caster is out of uses; it disappears when the caster drops to 0 DP; no heals on a summon; it acts right after your turn. The app today: calling costs a use, 1 DP drain per round (`campaign_websocket.py` ~5017), acting is free (the Act button just shipped), a summon survives its summoner going down. This is a rework of what we shipped today and the day before, not a patch. It also settles the open questions (drain vs the Calling, summon outliving its summoner). |
| Not in report | Damage Effects | Poison/burning/bleeding as damage over time is a new mechanic. Nothing exists. |
| Not in report | Defense roll for debuffs | Core says (Buffs and Debuffs) the target rolls **1d6** + stat + Edge; Core (Area of Effect) says each target rolls **its defense**. The app uses the Defense Die. See question 3. |
| Confirmed matching | Edge/BAP 1-10, defense die by level, BAP one roll never banked, Calling at -10, SW difficulty die by level, "defender adds the same stat" for spells (attack and debuff), summon durability by level, Combo cancel at 0 DP (once per encounter). |

## 2. Plan

Each phase is its own commit (or small group), deployable alone, with tests. I would ship them to production one at a
time, not as one big drop, because prod is played daily.

**Phase 0: docs only.** Replace `Rulebook.md` and `LevelingTable.md` with v3.1 (Adult). Update `CLAUDE.md` rules line.
No risk.

**Phase 1: The Calling (small, behavior only, no migration). DONE on branch rules-v3.1, not yet on main.**
- Tie is Marked (survive at 1 DP), not death. `routes/character_fastapi.py` `resolve_the_calling`.
- `times_called` counts Marks only; a clean return does not count; the 5th Mark kills instead of the 5th entry.
  Remove the instant permadeath at the 3 entry sites; the roll decides, and a Mark at count 4 means death.
- Scar or fear becomes a Tether; a limitation just stays (today scars go in `battle_scars`).
- Tests: tie, clean return does not count, 4 clean returns then 5th Calling still rolls, 5th Mark dies.

**Phase 2: one source of truth for the numbers. BUILT on branch rules-v3.1-phase2 (not on main until the prod migration is approved).**
Deviation from the plan: the pages do not fetch the numbers from an endpoint. They are static files with
top-level consts read at load, so making them async would be risky in a 14k-line page. Instead the backend reads
`schemas/leveling_v3_1.json` and `tests/test_leveling_tables.py` fails if any front-end copy drifts (it found two
extra hand-typed copies: the help table and the SW set-level popup). Shipping order: deploy the code, run
`scripts/migrate_rules_v31.py` (dry run first, then --apply, --undo available), then done.
- New `schemas/leveling_v3_1.json` (DP, Edge, BAP, defense die, weapon options, spell dice per slot, uses, Ally table).
- Backend reads it; the 5 front-end copies fetch it from a public endpoint (`/api/public/leveling`) instead of
  carrying their own tables. This removes the "stays in sync" problem for good.
- Numbers: DP 8 + 2/level, uses = level + 2, drop the four trap weapon dice, new buff table (+1,+2,+2,+3,+3,+4).
- Tests: update `tests/test_characters.py` (30 at L5 becomes 16, 35 at L6 becomes 18) and add table tests.
- Applies to new and leveled characters on deploy. Existing characters need Phase 2b.

**Phase 2b: migrate existing characters (needs a migration script, not a SQL file).**
- Your Oct 9 answer: migrate everyone, keep health as a percentage. Script: dry run first, old values saved in a
  new table so it can be undone, no summons or objects, anyone at DP <= 0 or in the Calling left alone, min 1 for living
  characters, current DP never above new max, run with no active encounter.
- Needs your answer on NPCs (question 5).

**Phase 3: shared uses pool (structural). BUILT on branch rules-v3.1-phase3, not yet on main.** Implemented with
`backend/uses.py` over the existing Character.max_uses_per_encounter / current_uses columns, so no migration is
needed (the Phase 2 migration already set both). Combo cost moved to 1 use per character here, since the same lines
changed (Phase 7 keeps the rest of the Combo work). Summons acting are still free until Phase 6.
- Casts spend from `Character.current_uses` (max `max_uses_per_encounter`); per-ability `uses_remaining/max_uses`
  stop mattering. The ability list shows one pool number. Encounter end and rest restore the pool.
- Migration: set each character's pool from the new table and current pool from the existing abilities'
  remaining, capped. Additive; old columns stay.
- Allies get their own pool the same way.

**Phase 4: buffs and debuffs. BUILT on branch rules-v3.1-phase4, not yet on main.** Audit finding while building it:
spell rolls ignored buffs and debuffs entirely (only weapon attacks and checks read them, and basic attacks summed every
stat's effects together). `backend/buffs.py` now supplies `effect_modifier` (strongest buff plus strongest debuff on the
roll's stat), `add_effect` (replaces same sign and stat) and `tick_round` (per round).
- Duration 2 rounds, counted per **round** (decrement when the round number changes), so a +N lasts the rest of the
  cast round and the whole next round. One buff and one debuff per stat per target; a new one replaces the old; both
  apply to the roll (net). Apply to all five creation sites above.
- Tests: replace, net, expiry across a round change, Boost/Stat Check effects.

**Phase 5: healing. BUILT on branch rules-v3.1-phase5, not yet on main.** Needs migration 034 (the `encounter_heals` table,
applied automatically on deploy). Reading of the rule worth confirming with Jason: "after the encounter, healing is free"
is implemented as: with no encounter running, a heal spell costs no use and has no once-per-person limit.
- Roll spell die + stat + Edge; once per caster-spell per target per encounter (new small table keyed by encounter and
  target, cleared when the encounter ends); at negative DP reset to 0 then add; no heals on summons; potions and rest
  do not count. Shows a "Healed this encounter" mark on the target.
- Needs a migration (new table).

**Phase 6: summons rework. BUILT on branch rules-v3.1-phase6, not yet on main.** No migration. Hooks that make a summon
vanish when its summoner drops to 0 DP cover weapon attacks and spell damage immediately, plus a safety net
(`_cleanup_orphan_summons`) at every turn advance and whenever the summon tries to act, so Env Check damage and the SW's
manual damage are caught too, just not instantly.
- Free and instant to call (no use, no action); each round it acts spends 1 shared use; out of uses it fades;
  summoner at 0 DP removes it; remove the DP drain and its notice; acts right after the summoner's turn
  (initiative row stays, the Act button stays, now spends a use); no heals on a summon.
- Rewrites parts of `tests/test_summon_cast.py` (the "no use charged" and drain tests invert).

**Phase 7: Combos. BUILT on branch rules-v3.1-phase7, not yet on main. No migration.** Decisions made while building (Jason
asked for automation, not a design review): each player picks a target when the Combo fires; a Combo buff or debuff counts
one step higher ONLY when the Combo has no attack (Jason, Nov 17: stick to the book); two same-stat effects: the stronger wins; the Triple Combo gate is now
level 11+ so it is dormant until Ascension (Phase 9); the once-per-encounter check covers two-person Combos only (the Triple
is already one-shot by its three-way hold); picked targets live in process memory for the few seconds between the picks and
the resolve; if they are lost (a restart) nothing is rolled, spent or marked fired and everyone is asked to pick again; the use
and the fired flag are committed together with the result card.
- Cost 1 use per character (Combo and Triple), Triple needs level 11+ (so it stays dormant until Ascension) and gets +2
  on every roll, and the card shows "heal adds BAP" and "buff/debuff one step up" as numbers. Whether Combos also apply
  their damage and effects automatically is question 4.

**Phase 8: Allies and Tethers. BUILT on branch rules-v3.1-phase8, not yet on main. No migration** (prod has no Allies, and Tethers
live in the existing JSON column). Decisions: a Marked scar or fear creates the Tether automatically (the SW picks the kind and
-1 to -4 strength); a limitation just stays on the sheet; an ACTIVE Tether rides the Calling roll like every other roll
(the SW switches it on when it fits the moment); an Ally's owner gets Emptiness (inactive until the SW switches it on),
other Bonded characters get Grief (active), every Combo with the Ally is lost. Ally table (DP 4 to 13, slot 1 die from level 1, own pool, cap 10); Tether scale +1 to +4,
strongest bonus and penalty only, Grief -1 to -3.

**Phase 9: Ascension (levels 11 to 15). BUILT on branch rules-v3.1-phase9, not yet on main. Needs migration 035** (`abilities.secondary_effect`,
additive). Decisions (Jason, Nov 17): secondary effects are STRUCTURED with a free-text note: {kind: debuff|buff|note, stat, strength
1-4, note}. A debuff lands automatically on a hit and replaces the old one on the same stat; a buff goes to the caster on an
attack or debuff and to the one helped on a heal or buff; a note-only effect is applied by hand. Not automated: an Ally's own
secondary effect (the level 11 effect when slot 1 is an Ally), Ascension Combo evolution (a table event), and a secondary
effect on an AOE reaches the targets the SW approved for the cast. Everything capped at 10 today. Edge/BAP/DP rows, one secondary effect per
Ascension level per slot, Calling difficulty bonus, Triple Combo, level cap 15 (Allies stay at 10).

**Later (own plans):** Damage Effects; Kids terminology mode; `static/*.html` rules text if any shows old numbers.

## 3. Tests that will break
- `tests/test_characters.py` lines 120, 121, 174, 175 (DP 30 and 35).
- `tests/test_summon_cast.py`: the "costs no use / no drain" assertions and `test_summon_commands_work_with_no_uses_left`
  invert in Phase 6; the 1-use summon cost in Phase 3.
- Any test that builds an ability with `max_uses=3` and reads `uses_remaining` (`test_ability_cast_speaker.py`,
  `test_bap_per_roll.py`) in Phase 3.
- New tests are listed per phase.

## 4. Questions for Jason
1. **Shared pool. ANSWERED (Nov 17, Jason): yes, one total pool across all spells and techniques.** Original question: OK to retire the per-ability uses counters in favor of one pool per character?
2. **Existing `times_called`. ANSWERED (Nov 17):** moot. A read-only prod query shows 0 of 19 characters have any
   Calling history (times_called, in_calling, is_called, scars all zero), so Phase 1 needs no data cleanup.
3. **Debuff defense. ANSWERED (Nov 17, Jason):** the target rolls **1d6 + the same stat + Edge**, not the Defense
   Die, because armor shouldn't block things like Fear or Confuse. The app uses the Defense Die today, so Phase 4
   changes it (ability debuffs, and any SW-applied debuff path). Open wording nit for Jason: the Core's Area of Effect
   paragraph still says "each target rolling their defense" for debuffs; it should say 1d6 + stat + Edge to match.
4. **Combos in the app. ANSWERED (Nov 17, Jason): automate.** Own phase after the basics (cost, Triple +2 and the level gate ship first). Original question: Keep them as roll totals the SW applies (cheapest), or automate target, defense, damage, buff
   and heal effects (a real feature, probably its own phase)?
5. **NPCs on the migration. ANSWERED (Nov 17, Jason): migrate all NPCs.** Hand-set boss DP will move to the table value; tell the SW to re-tune after. Original question: Convert every NPC to the new table, or only ones built from the table (not hand-set DP)?
6. **Buff timing. ANSWERED (Nov 17, Jason): round-based, the cast round plus the next.** Original question: I plan to count rounds (the cast round plus the next), not each character's own turn. Fine?


## Finish-v3.1 extras (after Phase 9)

- **Damage Effects: BUILT on branch rules-v3.1-extras, not yet on main. Needs migration 036** (`active_effects.data`).
  Effect type `dot` ("Damage Effect"): cast like a debuff, defended with 1d6 + stat + Edge; if it lands the target takes the spell
  die once at the start of their next turn (resolved automatically by the server, resist for half rounded down), it can reach -10
  and The Calling, a new one replaces the old one, a summon cannot be hit by one. Boost works on it. Side fixes found on the way:
  a cast where no target was rolled for no longer spends a use; the NPC ability editor saved "healing", which casting never
  recognised, so it now saves "heal" (old rows are treated as heals).
- **BAP effect: not built, waiting on Jason.** It is in the SW Guide, not the Core: a BAP moment can also give +1 or -1 until the
  start of the target's next turn, the SW picks the stat, same one-per-stat rule. The SW can already do this by hand with the
  Add Effect button.
- **All-or-nothing Combo save (Option A): BUILT on branch rules-v3.1-atomic-combo, not yet on main, no migration.** `_all_or_nothing` in
  `routes/campaign_websocket.py` wraps both Combo resolvers: every `db.commit()` inside only flushes, everything that would be
  broadcast or sent to a player is held, and one real commit (damage, heals, effects, summons vanishing, a Calling starting, the uses,
  the fired flag and the result card) happens at the end, after which the held messages go out in order. Any failure rolls it all
  back and re-prompts the players with "Nothing was spent or changed". Known leftover: a web push notification sent from inside the
  Calling trigger is external and cannot be taken back.


## Final read-through (Nov 17): what it found

Fixed on branch rules-v3.1-readthrough (no migration):
- Potions: Tier 5 heals 14 (was 12); buff potions use the +1 to +4 table for 2 rounds (was +1 to +6 for as many rounds); potions and the
  SW's manual heal wake someone at negative DP (0 first, then add); a potion cannot heal someone in The Calling. The potion table now lives in
  `schemas/leveling_v3_1.json` with a drift test against the page.
- Environmental Healing also wakes from negative DP.
- A character at 0 DP or below cannot cast (the rules say they can't act until healed; weapon attacks already enforced it).
- Ascension "cleanse one debuff" secondary effect (the Guide's own example).

Not changed, waiting on Jason:
- Weapon attacks on a character already at 0 DP are refused by the app ("already unconscious"). The rules do not forbid it, and the
  dice engine even supports it (an unconscious defender rolls no defense), so without it only a single big hit, a spell or a Damage Effect
  can take a downed character to -10. Allow attacks on the downed?
- Enemy Combos (NPC pairs): the app has no way to hold an NPC's turn for a Combo; the SW does it by hand today.
- Swarms ("cannot be healed, DP are bodies"): no swarm flag; the SW just does not heal them.
- An Ally dying should always leave a Memory Echo: the SW is prompted in the Calling window, but the app does not force it.
- Ally secondary effects (level 11 effect on an Ally in slot 1) and Ascension Combo evolution stay table events.
- Vehicles are not in the app at all.
- BAP effect (+1/-1 for a round on a BAP moment): not built, SW can use Add Effect.
