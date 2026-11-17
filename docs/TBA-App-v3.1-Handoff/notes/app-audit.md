# TBA companion app vs v3.1 rules: gap report (Nov 9, 2026)

Source: `Klutzleo/TBA-App`, `main` at 1dc3714 (Nov 4). I read the code (read only). I did not run the app, and I changed nothing. The rules docs are the source of truth, so every row below is "the app should change", not the reverse. `CLAUDE.md` and `PROJECT_STATUS.md` say the app is on v3.0 and that Ascension, then "a possible rules revision", are next. v3.1 is that revision.

## Already matches v3.1

- Edge and BAP for levels 1 to 10 (`schemas/core_ruleset.json`).
- Defense die by level (`get_defense_die`).
- Combo cancellation (a partner at 0 DP cancels, costs nothing), once per encounter, Triple Combo at level 11+.
- Calling triggers at -10 DP; SW difficulty die by level (1d6, 1d8, 1d10, 1d12); player rolls 1d6 + IP or SP + Edge (+ BAP).
- BAP applies to one roll and is never banked.
- Summon durability by level (1 hit at levels 1 to 3).

## Needs to change

| # | Area | v3.1 | App today | Where |
|:-:|:--|:--|:--|:--|
| 1 | Damage Points | 8 at level 1, +2 per level (8 to 26 at level 10, 36 at 15) | 10 at level 1, +5 per level (10 to 55) | `backend/character_utils.py` `DP_BY_LEVEL`; tests expect 30 at L5, 35 at L6 |
| 2 | Uses per encounter | Level + 2, one shared pool | Level x 3 (3 to 30); also a per-ability `max_uses` default of 3 | `character_fastapi.py` (lines ~215, 948, 1037), `models.py` |
| 3 | Weapon dice | L1-2: 1d4. L3-4: 1d6 or 2d4. L5-6: 1d8 or 2d6. L7-8: 1d10, 2d8 or 3d6. L9-10: 1d12, 2d10 or 3d8 | Also offers 3d4, 4d4, 5d4, 4d6 | `get_available_attack_styles` |
| 4 | Buff and debuff size | 1d6 +1, 1d8 +2, 1d10 +2, 1d12 +3, 2d6 +3, 2d8 +4 | +1, +2, +3, +4, +5, +6 | `BUFF_DEBUFF_TABLE` in `campaign_websocket.py` (line ~1515) |
| 5 | Buff and debuff duration | 2 rounds (the cast round and the next) | Lasts as many rounds as its modifier (a +3 lasts 3 rounds) | `campaign_websocket.py` (~2034, ~2128) |
| 6 | Buff and debuff stacking | One buff and one debuff per stat per target; a new one replaces the old; buff and debuff on the same stat net out | No replacement found; debuffs are summed | `ActiveEffect` handling (~1291, ~3146) |
| 7 | Healing | Spell die + stat + Edge, like any spell (changed Nov 10); once per encounter per target; free after the encounter | Die + power stat (no Edge); no once-per-encounter check found | `campaign_websocket.py` (~2005) |
| 8 | Calling outcomes | Win by 4+: clean. Tie or win by 1 to 3: Marked. Lose: dies | Margin 4+ clean, 1+ scarred, otherwise dead, so a tie kills | `character_fastapi.py` (~2339) |
| 9 | Allies | Own table: half DP (4 to 13), own Edge, BAP and dice, slot 1 from level 1, own uses, stops at level 10 | Ally is built with the player table (code says "Allies use different leveling table - TODO"), so full DP | `create_ally` (~1731) |
| 10 | Tethers | Own scale +1 to +4; if more than one applies, only the strongest bonus and strongest penalty count, and you take the difference; Grief is -1 to -3 | Grief clamped -5 to -1; stacking rule not found | `routes/bonds.py`, `_active_tethers` |
| 11 | Ascension (levels 11 to 15) | DP 28 to 36, Edge 5 to 7, BAP 6 to 8, one secondary effect per level; Calling roll +1 at 13 to 14, +2 at 15 | App cap is level 10 | many sites (already planned) |
| 12 | Rule text in the repo | v3.1 Core and Leveling Table | `Rulebook.md` and `LevelingTable.md` are v3.0 | repo root |
| 13 | Combos (changed Nov 10) | Every Combo costs 1 use per character, Triple Combo too (was 2 and 3). A Combo with no attack: the heal adds the healer's BAP, and a buff or debuff counts one step higher on the buff table (+4 max). Heals still follow once per person per encounter | Combo cost is 2 uses per character (3 for Triple) | combo handling in `campaign_websocket.py` |

## Not changed in v3.1 but worth a look

- **Legacy `backend/magic_logic.py`** uses old rules (defender adds Physical, Calling at -5, buff added to the spell roll). The live path is `campaign_websocket.py`. Make sure it is truly unused before anyone ports it.
- **BAP on multi-die weapons.** v3.1 says BAP goes on one roll of the action, and you say which die. I saw the one-roll behavior, but not how it handles multi-die weapons. `tests/test_bap_per_roll.py` is where to check.
- **"Your Turn" and "casting takes your turn".** The app doesn't enforce either. That's probably fine, since turns are a table agreement, but a one-line hint in the UI would help.
- **Kids edition.** The app only has the "Lore for Being Awesome" label. There is no Kids terminology mode (The Challenge, Battle Scarred, knocked out for good). This is a product decision.
- **Area-of-effect defender stat and hazard half damage.** I did not trace these.

## Suggested order (smallest risk first)

1. Replace `Rulebook.md` and `LevelingTable.md` with v3.1, and fix the Calling tie (row 8). Small and self-contained.
2. Numbers only: DP, uses, weapon dice, buff table (rows 1 to 4). Update the tests that expect the old DP.
3. Behavior: buff and debuff duration, stacking and netting, healing (rows 5 to 7).
4. Allies and Tethers (rows 9 and 10).
5. Ascension (row 11), which is already the next milestone.

Existing characters and campaigns need a plan: DP and uses change, so the existing rows would need a migration, or the new rules apply only to new characters. That is a decision for you.
