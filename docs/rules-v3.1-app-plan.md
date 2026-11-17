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

**Phase 1: The Calling (small, behavior only, no migration).**
- Tie is Marked (survive at 1 DP), not death. `routes/character_fastapi.py` `resolve_the_calling`.
- `times_called` counts Marks only; a clean return does not count; the 5th Mark kills instead of the 5th entry.
  Remove the instant permadeath at the 3 entry sites; the roll decides, and a Mark at count 4 means death.
- Scar or fear becomes a Tether; a limitation just stays (today scars go in `battle_scars`).
- Tests: tie, clean return does not count, 4 clean returns then 5th Calling still rolls, 5th Mark dies.

**Phase 2: one source of truth for the numbers.**
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

**Phase 3: shared uses pool (structural).**
- Casts spend from `Character.current_uses` (max `max_uses_per_encounter`); per-ability `uses_remaining/max_uses`
  stop mattering. The ability list shows one pool number. Encounter end and rest restore the pool.
- Migration: set each character's pool from the new table and current pool from the existing abilities'
  remaining, capped. Additive; old columns stay.
- Allies get their own pool the same way.

**Phase 4: buffs and debuffs.**
- Duration 2 rounds, counted per **round** (decrement when the round number changes), so a +N lasts the rest of the
  cast round and the whole next round. One buff and one debuff per stat per target; a new one replaces the old; both
  apply to the roll (net). Apply to all five creation sites above.
- Tests: replace, net, expiry across a round change, Boost/Stat Check effects.

**Phase 5: healing.**
- Roll spell die + stat + Edge; once per caster-spell per target per encounter (new small table keyed by encounter and
  target, cleared when the encounter ends); at negative DP reset to 0 then add; no heals on summons; potions and rest
  do not count. Shows a "Healed this encounter" mark on the target.
- Needs a migration (new table).

**Phase 6: summons rework.**
- Free and instant to call (no use, no action); each round it acts spends 1 shared use; out of uses it fades;
  summoner at 0 DP removes it; remove the DP drain and its notice; acts right after the summoner's turn
  (initiative row stays, the Act button stays, now spends a use); no heals on a summon.
- Rewrites parts of `tests/test_summon_cast.py` (the "no use charged" and drain tests invert).

**Phase 7: Combos.**
- Cost 1 use per character (Combo and Triple), Triple needs level 11+ (so it stays dormant until Ascension) and gets +2
  on every roll, and the card shows "heal adds BAP" and "buff/debuff one step up" as numbers. Whether Combos also apply
  their damage and effects automatically is question 4.

**Phase 8: Allies and Tethers.** Ally table (DP 4 to 13, slot 1 die from level 1, own pool, cap 10); Tether scale +1 to +4,
strongest bonus and penalty only, Grief -1 to -3.

**Phase 9: Ascension (levels 11 to 15).** Everything capped at 10 today. Edge/BAP/DP rows, one secondary effect per
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
1. **Shared pool.** OK to retire the per-ability uses counters in favor of one pool per character?
2. **Existing `times_called`.** It currently counts clean returns too, so some characters read higher than the Mark
   count. Leave as is, or reset to the number of Marks (their `is_called`/scars history)?
3. **Debuff defense.** Core says the target rolls 1d6 + stat + Edge; the Area of Effect text and the app use the
   Defense Die. Which is right?
4. **Combos in the app.** Keep them as roll totals the SW applies (cheapest), or automate target, defense, damage, buff
   and heal effects (a real feature, probably its own phase)?
5. **NPCs on the migration.** Convert every NPC to the new table, or only ones built from the table (not hand-set DP)?
6. **Buff timing.** I plan to count rounds (the cast round plus the next), not each character's own turn. Fine?
