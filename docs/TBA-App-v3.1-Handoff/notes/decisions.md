# TBA v3 and v3.1: Decisions Log

One log for every rule decision, oldest first. Part 1 is the Oct v3 audit work. Part 2 is everything since (Nov 5 to Nov 9, 2026), merged from the old addendum. Where Part 2 changes a Part 1 item, Part 1 says **[Superseded]** or **[Updated]**.

**Current headline rules (v3.1, Nov 9):** DP 8 at level 1, +2 per level. Uses = level + 2. Buff/debuff table +1 to +4 keyed to spell die, 2 rounds (you get one action with it, it ends at the start of your turn after that), casting takes your turn. Heals roll spell die + stat + Edge, once per person per encounter. Tethers +1 to +4, strongest bonus and penalty only. BAP once per action. Combos cost 1 use each (Triple too) and give free BAP; Combos without an attack move buffs and debuffs one step up (heals get the free BAP like any roll). Summons are instant and free to call; each round one acts costs 1 use, which is its upkeep (no DP drain). Damage Effects (poison, burning, bleeding) can take you to -10 and The Calling. Items have no bonus cap. Allies: half DP, own uses, slot 1 from level 1.

## Part 1: Oct 1 to Oct 7 decisions (v3 audit)

Running list of rule decisions made while working through `tba-v3-audit.md`. Items marked **[Superseded]** were changed later; see Part 2 for the current rule.

### LOCKED (Oct 1, 2026)

#### Section 1: Fix-now list
- **#1 Level 1 gear:** start with 1d4 weapon and 1d4 armor (matches the Leveling Table).
- **#7 Combo cancellation:** only dropping to 0 DP cancels a Combo (SW Guide version). Update Core. **[Superseded Nov 5:** either partner dropping to 0 DP cancels a two-person Combo.**]**
- **#8 The Called:** only characters Marked by Death gain it (Core version). Update SW Guide.
- **#13 Buff cap:** superseded, see Decision C (one buff + one debuff per stat).
- **No-brainer fixes approved:** #2 Ally DP text; #4 Triple Combo = level 11+; #5 Edge wording; #6 Vehicle Edge range; #10 Emptiness value; #12 debuff roll in Core; #14 Potion T5; #15-16 sheet/Ally table gaps; #18 regenerate Sept Leveling Table.
- **#9 Tether cap:** 1-3 **story** Tethers per character. Marked by Death, Grief, and Emptiness are extra and do not use those slots. Update Core and SW Guide (the SW Guide's "1-3 total over the whole campaign" wording goes).
- **#11 Memory Echo:** always created for a **heroic death** or an **Ally's death**; any other death only if the SW wants one. The "3-5 per campaign" limit becomes a tip, not a rule. Update Core ("any death") and SW Guide.
- **#3 Ally stats:** 3/2/1, covered under Allies below.

#### Pacing (Decision A)
- **DP = 8 at level 1, +2 each level:** 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36.
- Damage unchanged (the difference of the two rolls). No doubling, no per-hit math.
- **The Calling stays at a flat -10.** Sim: 0% of 4v4 fights through L5, about 9% at L10+.
- Why 8: the biggest single hit at L1 is 7 (1d6 spell + stat 3 vs a PP 1 defender), so nobody goes down from full health in one hit. L1 fights run about 6 rounds, and fights run about 6-10 rounds at every level (today: 7 at L1 up to 21 at L15).
- Table changes: DP row; "+5 per level" text becomes "+2 per level"; Ally DP about half (4 at L1); Vehicle DP matches the PC row.
- Rejected: 2x damage (extra math, Calling scaling), halving DP (5 DP at L1 can go down in one hit), single-hit cap, casters at 1d4+1 (class-specific special rule).

#### Healing (Decision B)
- Spells/techs can heal a given character **once per encounter**. **Heals roll the die only** (no stat, no Edge). **[Superseded Nov 10: heals now roll spell die + stat + Edge, like any spell. One heal per person per encounter stays.]**
- Potions and rest do not count toward the cap.
- After the encounter, healing is free, but players must say it out loud, and the SW can say there's no time.
- Flavor, genre-neutral: "fast fixes don't stack." Per-genre flavor lines go in the SW Guide. Potions are rewards, not a supply line.
- Sim (4v4 same level, healer in party): 59-69% win across L1-L15 (about 65% from L3 up) (no healer: 50%; uncapped full-roll heals: 96-100%).

#### Allies
- Stats **3/2/1** (same as a normal character). DP about half of the player's. Spell die from their slot-1 equivalent starting at **level 1** (not level 3).
- Don't match Ally Edge to the PC.

#### Buffs and debuffs (Decision C)
- **[Superseded Nov 9: new table, +1 to +4, see Part 2.]** Every buff or debuff lasts **2 rounds**, whatever the die. Replaces "lasts rounds equal to the modifier." Update Core, SW Guide (buff/debuff tips and example), and the potion tier table.
- Applies to players and enemies equally. Tethers are not time-limited (no change). **[Superseded Nov 9: Tethers have their own +1 to +4 scale.]**
- **LOCKED (supersedes #13):** one buff and one debuff **per stat** (IP/PP/SP), tied to the stat of the roll they change. Both apply at once. New on the same stat replaces old. Tethers don't count. Non-roll effects (speed, blind): SW picks the stat. Combos stack naturally across stats; same-stat Combo effects: newer replaces older.
- Note: even at 2 rounds, buffs/debuffs outran damage spells at higher levels with the old table. Fixed by the Nov 9 rebalance.

#### BAP and Combos (Decision D)
- **No BAP cap.** Keep +1 to +8 as written. BAP is rare and SW-controlled, and it's meant to stack with Tethers, items and buffs. Add an SW Guide line: "BAP is for moments. If it's showing up every round, it isn't a moment."
- **Each Combo can be fired once per encounter** (applies to Ally Combos, Triple Combos, and enemy Combos). This restores the "burn it now or save it for the boss" tension. Combos still grant full BAP automatically. **LOCKED (re-confirmed):** Combos keep the uses cost too: 2 uses per character (4 total), Triple 3 each (9 total). Weapons stay free. Revisit in playtesting if it feels clunky.

#### Weapon dice and damage spells (audit 2.6)
- **Cut the four trap weapon options: 3d4, 4d4, 5d4, 4d6** from the Leveling Table (never best in any scenario). Remaining options: L5 1d8 / 2d6; L7 1d10 / 2d8 / 3d6; L9 1d12 / 2d10 / 3d8. Update the Leveling Table (all copies), Character Sheet, and companion app if it lists them.
- **Rewrite Core's "Risk vs Reward" blurb** (it had the math backwards): more dice = more swings and fewer wasted turns; a single big die is a bet that either hits hard or whiffs.
- **Damage spells stay as they are.** Their value is flexibility (heals, buffs, AOE), not raw damage.

#### Vehicles (audit 2.10)
- **Restore the dropped v2.0 vehicle text** into Core: "use the vehicle's Edge instead of your own"; the maneuvers roll (1d6 + PP + Vehicle's Edge); Vehicle vs Person combat (vehicle Weapon Die + PP + Vehicle's Edge vs the person's Defense Die + PP + Edge; vehicle defends with its Defense Die); vehicle systems and examples (shared uses per encounter); the Multi-Crew Combat Round (each crew member acts on their own initiative; unmanned stations do nothing; no armor officer = base Defense Die only); and crew damage only on a hull breach or direct crew hit.
- **Keep vehicle Edge 0-10 and vehicle DP = PC DP row (8 at level 1, +2 each level).** Vehicles are set pieces by design. Fix the table/text mismatch (Edge range 0-10 vs table's 1-10).
- **SW Guide tip:** a person on foot can't win by trading blows with a same-level vehicle. Give them a way in: sabotage, hacking, boarding, or terrain.

#### Uses per encounter (audit 2.12)
- **Uses = level + 2** (L1 3, L3 5, L5 7, L10 12, L15 17). Replaces "3 per level." Covers every spell/technique cast (attacks, heals, buffs, debuffs); weapons stay free; Combos still cost 2 uses per character. Reason: fights run about 8 rounds, so a 30-45 pool never mattered after about L3.
- Update: Core (Magic & Techniques, Leveling), Leveling Table (all copies and the PDF), Character Sheet, Ally/Vehicle tables.

#### Dropped items to restore (audit section 6)
- **Ally details (v2.0):** Allies can learn spells/techniques from their own slots, can earn BAP, and the wolf (PP 3) / owl (IP 3) stat examples.
- **Potions: take the max, no roll** (Tier 1 = 6 ... Tier 6 = 16). Do NOT restore "tiers double as buff round-length."
- **Swarm rules (v1.5):** swarms can't be healed and their DP are bodies. Use the original v1.5 wording so it's in Jason's voice.
- **Usable vs consumable items (v1.5):** two lines, use the original wording.
- Stay cut: crit/fumble (Fail Forward and BAP cover it), weapon/armor proficiency, casting cost in DP.

#### Rule gaps (audit section 3), one by one
- **#1 Area spells/techniques:** roll once; each target defends with its own defense roll. Allies caught in the area defend too. Heals and buffs need no defense; debuffs use the normal contest, per target.
- **#2 Ties:** ties go to the defender on debuffs and contested rolls. **In The Calling, a tie means you survive but are Marked by Death.**
- **#3 Healing limits:** DP can never exceed max. Healing someone at negative DP **resets them to 0 first, then adds the roll** (a heal always wakes you; -6 + a roll of 4 = 4 DP).
- **#4 Hazard resist:** the SW rolls the hazard; the player rolls 1d6 + stat + Edge. Beat or tie the hazard roll and take **half the damage (round down)**. One hazard roll is both the difficulty and the damage.
- **#5 BAP:** the SW can grant BAP on **any roll, defense included**. It stacks with Edge, buffs, items, and Tethers. NPCs only get BAP on their Combos.
- **#6 Summons:** a summon acts right after its caster's turn (no extra initiative slot). Each summon action costs **1 of the caster's uses**. It defends with the caster's Defense Die + IP + Edge. A "hit" is any attack that beats that defense roll and would deal damage. Upkeep stays -1 DP per round. **[Updated Nov 9: calling a summon is now instant and free, see Part 2.]**
- **#7 Buffs on multi-die weapons:** a flat buff applies to **each die**, the same as Edge.
- **#8 Cancelled Combo:** costs nothing (uses are only paid when it fires) and doesn't count toward the once-per-encounter limit, so it can be tried again.
- **#9 The Called count:** +1 each time you're Marked by Death. A clean return (win by 4+) doesn't count. If you'd be Marked for the 5th time, you die instead. The count stays even if you cleanse the status.
- **#10 Allies:** own pool of **level + 2 uses**, own initiative (the player rolls it), dice from the Ally Leveling Table with the slot-1 die from level 1. **Allies stop at level 10;** the Ally Combo evolves when its partner reaches Ascension.
- **#11 Memory Echo:** story first. If the SW wants it to matter mechanically, use a Tether-style buff (+1 to +3 on the Tether scale) when the party acts on it. Remove "narrative AND mechanical" from the SW Guide.
- **The Calling, Marked survivors:** a character who wins by 1-3 returns at **1 DP**, same as a clean return (win by 4+). The difference is the permanent Mark.
- **Already settled elsewhere:** rest/recovery (post-encounter healing is free, said out loud), vehicle Edge (vehicle's Edge instead of yours), crit/fumble (stay cut).
- **Potion Tier 5:** bump to 14 DP so it no longer equals Tier 4 (12). Tier 6 stays 16.

#### Section 4: useless / underperforming ideas
- **Pets:** keep as a short sidebar (two or three lines of story color, no mechanic).
- **The Called +1:** change the check to **1 = Nightmare (-1 next roll), 2-5 = nothing, 6 = Prophetic vision (+1 next roll)**, so keeping the status is a fair gamble. Update Core and SW Guide.
- Already handled elsewhere: uses per encounter (level + 2), single-target damage spells (leave), trap dice (cut), Potion T5 (14 DP), Vehicle DP (set pieces), Character Sheet Bond slots (note Bonds are unlimited).

#### Encounter design (Decision E): replaces the SW Guide's "Balancing Combat" rules of thumb
- **Threat points.** Add up every enemy's threat. Compared to the party's level: 3 lower = 1/4, 2 lower = 1/2, 1 lower = 3/4, same = 1, 1 higher = 1 1/2, 2 higher = 2, 3 higher = 3, 4 higher = 4, 5 higher = 5.
- **Budget = number of players.** Sim (final rules, no BAP/Combos/buffs): at every party size from 2 to 6, the same number of same-level enemies as players is a coin flip (about 50%); one fewer wins 90-99%; one more usually loses.
  - Easy: threat at most half the number of players. Standard: players minus 1 (wins, about half the party's DP gone). Hard: equal to the number of players (coin flip; a healer lifts it to about 65%). Deadly: more than the number of players.
- **Warnings for the SW Guide:** past level 10 the dice stop growing, so a level 15 enemy is only about 2 threat to a level 10 party (for Ascension fights, use numbers, not levels). BAP, Combos, and buffs make players stronger than these numbers, so don't be afraid to push.
- Also update the calibration tips: "if players are dying, remove an enemy before lowering levels."

#### Notes for the Core Rules / SW Guide edits
- **Core's Ascension table hard-coded DP 60/65/70/75/80.** Replaced with 28/30/32/34/36.
- **NPC section line:** NPCs and enemies use the same tables. Give a creature a few abilities (attacks, heals, buffs, or debuffs) from the same slot rules, with dice from the Leveling Table.
- **SW Guide notes:** Hazards T4-T5 are for deadly moments (T5 2d8 averages 9 damage). Potions are rewards, not a supply line (T6 = 16 DP is large against small pools).

### Oct 2 to Oct 7 details
- **Grief Tether (Oct 2):** Jason wrote the text himself. -1 to -3 by severity, not permanent, applies to memories, people, places and things tied to the fallen (SW calls it), lifted through story. Emptiness follows the same rule (starts -1, up to -3).
- **Jason's first pass (Oct 2):** adopted his edits: intro bullets restored to the longer wording; "end of their origin"; "hard stop"; "legendary character"; technique roll lists Intellect, Physical, or Social; healing line "Your body can't receive any more healing."; Pets wording ("You can buy, raise, or find them"); Emptiness back to his wording (starts at -1, SW sets weight); Grief SW note adds a Grief bonus for facing the one who killed the fallen.
- **Oct 2 (re-added after Jason's pass):** Emptiness applies when the loss comes into play (up to -3); Grief bonus against the killer uses the same range (+1 to +3).
- **Oct 2 Core cleanup:** potions also wake you from negative DP; vehicle Captain/Pilot adds are one-time roll adds, not buffs; Ally Combo past level 10 grows through the player's Ascension abilities (Ally stays level 10). SW Guide note: The Calling is at -10 absolute, so at L1 (8 DP) it takes 18 damage to reach it.
- **Oct 2 SW Guide v3.1 draft written.** Applies every Core/SW Guide decision. Additions Jason approved by use: 3+ lower = 1/4 threat; mixed-level party uses the average; Healing genre lines; Potions and Items section. Swarm threat still undefined (suggestion: one enemy of the swarm's level).
- **Oct 2 Leveling Table v3.1 draft:** characters, Ally and Vehicle tables rebuilt from the June v3.0 table with all numeric decisions. DP wording: "8 at level 1, +2 each level" (8 to 36).
- **Oct 2 Character Sheet v3.1 draft:** 17 use boxes (level + 2 at level 15), per-stat buff/debuff tracker, Combo "used this encounter" box, extra-Tether box (Marked/Grief/Emptiness), Times Called out of 5.
- **Oct 2 Allies (Jason):** Allies can have Tethers (start with none, earn in play; a Mark becomes one). Anyone can Bond with an Ally, not just its player. Combos with an Ally: each player pays own uses, Ally pays from its own pool, once per encounter. Allies can't join Triple Combos (stop at level 10). Ally death: every Combo with them is lost; everyone Bonded gains a Grief Tether; the Ally's player also gets Emptiness. Allies use the regular Character Sheet. Known tradeoff: Allies fall behind on numbers at Ascension; their Combos keep them relevant.
- **Oct 7 Allies: LEFT AS DRAFTED** (Jason). Full story (Tethers, Bonds, Calling), lighter numbers (half DP, 2 slots, level 10 cap, costs slot 1). Revisit only after playtesting.

### Oct 7: Kids v3.1 drafts
- Kids term: "Being Awesome" replaces "Bad-Ass" (BAP initials stay: Being Awesome Power).
- Kids drafts made from Adult v3.1 with Kids v3.0 wording restored: Core, SW Guide, Leveling Table, Character Sheet.
- Same numbers as Adult. Kid terms: The Challenge, Battle Scarred, The Challenged, Bad Dream / Good Dream, "knocked out for good", Ally "sadness and loss" (no named Emptiness).
- Pets: "can get knocked out" (Jason, Oct 7). "Total Party Knockout" approved.
- Oct 7, Jason answered the Kids open items: Bad Dream roll stays 1 / 2-5 / 6 (same as Adult); Environmental Damage added to Kids Core, identical to Adult; Kids sheet box renamed "Grief / Sadness" to match the Core.

## Part 2: Nov 5 to Nov 9, 2026 (v3.1)

### Nov 5: Summons and the caster

- **If the caster drops to 0 DP, the summon disappears** (Jason). Healing the caster later doesn't bring it back; they summon it again (a spell use; since Nov 9, calling a summon is free and instant). Upkeep (-1 DP per round) can take the caster to 0, which also ends the summon. Left as is.
- Core wording (Adult and Kids): "If you drop to 0 DP, your summon disappears. Getting healed doesn't bring it back, you'll have to summon it again."
- Applies to Summons only, not Allies.

### Nov 5: Answers to the TBA App CC review (Oct 9)

Already fixed before the review: summon heal contradiction; Emptiness range; DP label; Ally Combo evolution wording.

Decided by Jason and written into both Cores, both SW Guides, and both sheets (where relevant):

1. **Combo cancellation:** either partner dropping to 0 DP cancels a two-person Combo. Cancelled costs nothing and can be tried again. (Matches Triple Combo.)
2. **Defending against spells:** the defender adds the same stat the attack used. SP attack vs SP, IP vs IP. Weapon attacks are PP vs PP.
3. **The Calling is immediate:** it happens the moment you hit -10. Nobody gets a turn to heal you first. (Replaces my earlier suggestion that a heal could stop it.)
4. **Two-buff Combo:** allowed, but the buffs can't stack. Put them on different stats or targets.
5. **Secondary effects:**
   - Debuff effects land automatically on a hit, no second roll. A new one on the same stat replaces the old one.
   - Area abilities: the SW decides which targets are reached (no map or movement rules).
   - Secondary effects deal no damage on their own.
   - Abilities unlock in slot order (slot 1 at level 11 through slot 5 at level 15). If slot 1 is an Ally or Summon, the level 11 effect goes to them and applies whenever they hit.
6. **Environmental resist:** unchanged (beat or tie = half, round down). Added: a hazard isn't an opponent, you can reduce it but not dodge it.
7. **The Calling at Ascension:** SW rolls 1d12 at levels 11-12, 1d12+1 at 13-14, 1d12+2 at 15. The bonus matches the Edge gained since level 10, keeping the odds at level-10 numbers (about 62% clean return, 8% death with a stat of 3).
8. **Small fixes:** potions heal "a set amount" (Tier 5 stays 14); "up to 3 story Tethers" (Core, Guide, both sheets); vehicle Edge "up to +10 instead of +7"; "Physical Edge" is just "Edge"; healing line now ends "...any more healing from spells or techniques."

Still open (not raised yet): vehicle DP at level 1 (a level 1 battleship has 8 DP; Vehicle DP = PC row is an earlier decision).

### Nov 5: Vehicles

Sim (hero PP 3, standard weapon, vs same-level vehicle): with someone on defense, one hero needs about 14 / 40 / 47 rounds (levels 1 / 5 / 10) to kill it. With nobody on defense (base die only), about 3 / 2.5 / 2.4 rounds at every level.

Decided by Jason:
1. **Unmanned ship keeps the vehicle's Edge:** a ship with no Defense Officer defends with its Defense Die + the vehicle's Edge, no character stat. (Sim: about 4 / 12 / 20 rounds for one hero.)
2. **"Vehicle or rider?":** when someone attacks a vehicle with a person on it, the SW asks which. An attack on the rider hits the rider; an attack on the vehicle hits its DP. Open vehicles (bicycles, motorbikes, horses) don't shield the rider. Enclosed vehicles (ships, tanks, mechs): crew only takes damage on a hull breach or direct targeting, as before.
3. **Size is story, not stats** (confirmed by Jason, Nov 5): a bike and a battleship at the same level have the same numbers; the SW gives a big ship the level that fits. Replaces "A Level 1 battleship starts powerful..." in the Core. Vehicle DP stays equal to the PC row.

Written into both Cores and both SW Guides.

4. **Disabling a vehicle** (Jason, Nov 5): sabotage, hacking, or a called shot is an attack roll against the vehicle's defense. On a hit the SW picks one system or the vehicle's movement, knocked out for 2 rounds, no DP cost. An Engineer can restore it early with a repair roll if the SW allows. Added as "Disabling a Vehicle" in both Cores and a tip in both Guides.

### Nov 5: Wording pass (Jason's voice)

- Removed all em dashes from both Cores and both Guides (commas, colons in lists, "-" in empty table cells).
- Cut AI-sounding lines; shorter healing wording ("You can't heal above your maximum DP."); no "That's your call"; healing genre bullets shortened to "a spell / a med-injector or nano-patch / a field medic"; "Hand them out as treasure."
- Risk vs Reward: dropped "two dice is the sweet spot" (revisit multi-die advice later); bullets now "More dice, more attacks" and "One big die is all or nothing."
- Hazards: new **Avoiding** paragraph (if a character sees a hazard coming they can try to get around it; the SW decides if it's possible). Resisting: "A hazard isn't an opponent, so you can reduce the damage but not dodge it once it hits."
- SW Guide: "If you want a fight to feel dangerous, use the stats of one level higher on the Leveling Table." (Jason said "tier"; I used "level" since tier means hazards and potions.)
- "Size is for flavor and story, not stats." The Calling is immediate: "No one can heal you first."
- Jason's own rewrites of the "It is not X. It is Y." lines in Core (Ascension intro, secondary effects, Bond, Combo) applied. SW Guide Ascension Calling bullet ("not a punishment") and Reavers example ("not in their stat block, just how they fight") also done.

### Nov 5: Design direction (Core Rules and sheets)

- **Look:** "Monolith" in the TBA app's colors: dark navy (#141828) and gold (#D4AF37) on the cover, openers and back cover; light bone (#F2EFE8) interior pages. Headings in Anton, body in Archivo. Genre-neutral on purpose (no fantasy or sci-fi theme).
- **Logo:** the TBA book-and-wrench mark, faint and large behind the cover title and chapter openers. The GameOctane logo stays small, back cover only ("its own thing").
- **Callout colors** (same as the app's combat log): red = damage and combat, teal = healing, purple = The Calling and Tethers, gold = Ascension and Leveling. Every box is titled so meaning never depends on color alone.
- **Built so far:** Core Rules v3.1 designed PDF (46 pages: cover, contents, 13 chapter openers, back cover) and a one-page Quick Reference, both built from the v3.1 rules text.
- **Decided, not built yet:**
  - Reference Tables appendix in the Core (lettered tables, page numbers filled in automatically), plus the same tables as separate printable sheets, generated from one source so they never drift.
  - Printer-friendly variants (white cover and openers, light header on the Quick Reference) for anything people are likely to print in black and white. The dark version stays as the screen PDF.
  - The companion app should be updated to match the v3.1 rules and the Quick Reference, not the other way around.
  - Kids Core and Kids Quick Reference in their own colors, after Jason's read of the Adult Core.

### Nov 5: Playtest-reader feedback round (Matias)

Applied to both Cores, both SW Guides (where relevant), and the Quick Reference:

1. **Leveling Table in the Core:** the full character table now sits in Chapter 5 (Leveling), before Ascension. (It was a separate document only.) Appendix plan stands.
2. **"Full BAP" in Combos:** now "each character adds their own BAP bonus (the number for their level) automatically."
3. **Triple Combo bonus:** every roll in a Triple Combo gets +2 (Jason chose to add a bonus).
4. **Bonds moved** to Chapter 7 (Pets, Allies & Summons): What is a Bond, Naming the Combo, Ally Combos. Combat keeps the Combo rules (new "Combo Attacks" section).
5. **The Calling (Kids: The Challenge) moved** to follow Combat. Added "(see Tethers)" pointer.
6. **Times Called table cleaned up:** the fifth-time rule is stated before the table, table has three rows, and the 1d6 check-in is its own list.
7. **Multi-crew vehicle table:** Effect column says what each roll is; Captain and Pilot results add on top of the Gunner's or Defense Officer's roll, they don't replace it.
8. **New Step 3 in Character Creation:** Choose Your First Spell or Technique (Equipment is now Step 4, Play is Step 5).

Combo examples replaced (Nov 9): Thunder and Lightning, Classic Misdirection, Overdrive, I Love This Plan!, We Got Your Back (Jason chose them; "I Love This Plan!" is flavor only, no extra mechanics). A short intro line was added above them.

### Buffs and debuffs rebalance (Nov 9, 2026)
- Table is now keyed to the spell die and tops out at +4: 1d6 +/-1, 1d8 +/-2, 1d10 +/-2, 1d12 +/-3, 2d6 +/-3, 2d8 +/-4. Only a first slot reaches +4, so slot 1 is always the strongest buff or debuff.
- Duration stays 2 rounds, now defined as the round you cast it and the next one, so a caster last in initiative still gets a turn with it.
- Casting a buff or debuff takes your turn (no attack that turn). Same for fighters who take one in slot 1.
- A buff and a debuff on the same stat both apply (+3 and -2 leaves +1). One of each per stat, new replaces old.
- Healing (spell die, potions) is untouched. Buff/debuff potion tiers follow the new table: Tier 3 +/-2, Tier 4 +/-3, Tier 5 +/-3, Tier 6 +/-4.
- Tethers moved to their own +1 to +4 scale (capped at 4 to match the top of the buff table; Nov 9) (no longer tied to the spell table), no duration. Memory Echo line updated to match.
- Why: simulated (4v4, realistic stat spreads, area slots, casting costs the turn). Old table (+1 to +6, 2 rounds) and longer durations made support too strong from level 7. About +2 for 2 rounds held near even at every level. Sim: sim_buffs11.py.
- Caveats: healing, the Calling and Combos not simulated. Two support characters are weak at levels 1-3. d8/d10 and d12/2d6 share a value. Watch in playtest.

### Wording fixes from the ChatGPT audit (Nov 9, 2026)
- New "Your Turn" section: move, one action (weapon attack, spell or technique, or Combo), interact if it makes sense; too much for one turn costs your action.
- BAP is added to one roll of your action. On a multi-die weapon you say which die gets it before you roll (changed Nov 9 after the sim showed per-die BAP doubled multi-die damage). BAP on the Calling/Challenge roll is added like any other.
- Ally and Summon both say "first spell or technique slot" (was "first technique" / "first spell slot").
- Failed hazard resistance = full damage.

### More audit wording (Nov 9, 2026)
- Combo cost stays 2 uses each. Reason (Jason): the free BAP. A massive move, both effects land, both add BAP automatically.
- Tethers: if more than one could apply to a roll, only the strongest bonus and strongest penalty count, and you take the difference (a +3 and a -4 = -1), like buffs and debuffs.
- SW Guide: new "Common effects" list (blind, slowed/hasted, stunned/dazed, confused/afraid, charmed/silenced) mapped to stats. No effect skips a turn; 2 rounds, one per stat. The "no turn skipping" line was Claude's call; Jason signed off Nov 10. Poison, burning, and bleeding were added to the list Nov 9 (see below).
- Kids age range: 6+ (Jason). Added to the Kids Core intro; SW note on adjusting The Challenge added to the Kids SW Guide (Jason approved the note's wording Nov 9).

### Math audit results (Nov 9, 2026; sim12.py, same-level mirror fights, 60k swings / 2,500 fights per cell)
- Multi-die weapons beat the single die on average damage at every level tested. Level 7: 1d10 1.7, 2d8 2.1, 3d6 1.7 avg per swing vs an equal defender; against a weaker defender 3d6 4.2 vs 1d10 2.8. Level 10: 1d12 2.0, 2d10 2.7, 3d8 2.6 (PP1 defender: 3.1 / 4.7 / 5.1). 2d8 and 3d6 are close; 2d10 and 3d8 are close. The single die is the weakest choice, by roughly 25 to 40 percent, mostly because Edge applies to every die.
- BAP on each die roughly doubles multi-die damage: level 10, 1d12 5.4, 2d10 8.9, 3d8 10.7. BAP once per action keeps all three about equal (5.4, 5.8, 5.3). Jason chose BAP once per action (below).
- Ally vs no Ally (4 characters + Ally, owner loses slot 1, vs 4 plain characters): level 1 61 to 71 percent, levels 3 to 9 51 to 55 percent. Close to even. Level 1 is the strong spot. Not modeled: the free Ally Combo, healing, Ally-specific stats beyond a wolf build. Enemies focus the lowest DP, which is hard on an Ally.

- Decision (Jason, Nov 9): BAP once per action, announce the die before rolling. Edge and buffs still apply to every die.

### Clarification lines (Nov 9)

Five small rules added to Core, Kids Core, and both SW Guides (Jason approved all five, with the item cap dropped and Tethers capped at +/-4).
- **Tethers and The Calling (The Challenge in Kids):** a Tether can add to or take from the roll, if the SW says it fits the moment. Same strongest-bonus, strongest-penalty rule.
- **Item bonuses:** no cap. Jason's call: loot is the reward, and the SW controls how much gear shows up. (Claude's +3 cap was dropped.)
- **Summons:** no heals (hits, not DP). Buffs and debuffs work on them like anyone, landing on Intellect.
- **Allies in Combos:** as many as it has Bonds. Each fires once per encounter and takes the Ally's action.
- **Speed effects:** slowed/hasted also change how far you can move. SW decides how much.

- **Poison, fire, bleeding (Nov 9):** damage over time, not a buff/debuff. Cast like a debuff (target defends). If it lands, the target takes the spell die once at the start of their next turn, can resist like a hazard for half. New replaces old. Added to Core, Kids Core, and the SW Guide's Common effects. Jason signed off on the wording and on the SW Guide's no-skipped-turn line (Nov 10); a stray multi-die sentence was cut from the paragraph. Sim (sim13): poison after the resist roll deals about 1.5 to 4.9 vs 2.2 to 4.2 for a normal attack, so it is a story pick, not an upgrade.

- **Summons: instant summoning (Nov 9).** Calling a summon is free (no action, no wait round) and it acts right after your turn, including the turn you call it. Upkeep (-1 DP per round) and 1 use per action stay. Sim (4 incl. a Summoner vs 4 plain, same level): as written 26 to 44% win; instant summoning 51 to 58% (Ally is 51 to 55%). Watch level 9 (58%). A version where calling still costs your turn only reached 33 to 50%.

- **Gemini audit (Nov 9):** two clarifications added to Core and Kids Core: a Tether is its own layer on top of buffs and debuffs on the same roll; area attacks are defended with the same stat the attack used. The "+41-4" Tether table typo it reported is not in the current files. Open: multi-crew vehicle uses (one shared pool for every station, per the earlier decision; Jason to decide if it drains too fast).

### Simulation results, round 2 (Nov 9, 2026; sim14 to sim18; Jason asked for sims in place of playtests)
- **Summons:** see "instant summoning" above. As written 26 to 44%; instant and free to call 51 to 58%.
- **Vehicles:** the shared uses pool never runs dry (ship fights last 2 to 4 rounds, pool 3 to 11). A bigger pool, or one per station, changes nothing. Crews who fire systems instead of doing their station job lose (17 to 39%). The Captain's add makes fights short; without it the Engineer's repair out-heals the Gunner. Jason decided to leave vehicles as written.
- **Combos (damage + damage, 4v4, 1,500 fights, one Combo per team):** single-target Combo 47 / 39 / 40 / 41 / 46% at L1 / 3 / 5 / 7 / 9 (a trap pick: the hold and the 2 uses cost more than the BAP gives back). Combo using an area slot against 3+ foes: 47 / 65 / 67 / 70 / 72% (strong). Cancelled during the hold in 8 to 16% of fights (L1 higher). Not tested: damage + buff, heal + debuff.
- **Full party vs threat labels (4 players; same-level plain enemies):** Easy (2 enemies) 90 to 97% win; Standard (3) 74 to 87%; Hard (4) 48 to 62%; Deadly (5) 25 to 39%. Adding a buffer, healer and Combo to the party helps a little at L7 to 9 (Standard 82 to 87%, Hard 56 to 62%). The labels hold.
- **Ascension:** 4v4 mirror fights run 4.6 rounds at L11 to 5.5 at L15 (4.4 at L10); The Calling triggers in 11 to 12% of fights at every Ascension level, same as L10. 4 level-10 players vs 1 level-15 enemy: 96% win; vs 2: 15% (so one L15 enemy is a bit more than the "about 2 threat" the guide says; about 2 to 2.5). 4 level-15 players vs 8 level-10 enemies: 92%.
- **Stacking (one spell swing vs an equal defender):** a +4 Tether roughly doubles damage per swing; buff + Tether +4 + BAP takes average damage from 2.1 to 10.0 at L5 (3.4 to 15.5 at L9) and one-shots a full-DP target 7.5% (L5) and 4.5% (L9) of the time. All three need the SW to grant a Tether and BAP, so it stays rare. No rule change. Guidance idea: a +4 Tether is for the biggest story moment.

### Combo changes (Nov 10, 2026; sim17 and sim19, 3,000 to 4,000 fights per cell)
Jason asked whether Combos are worth taking, since a Combo seemed to give only free BAP.
- **Single-target damage + damage:** about 40 to 47% win rate vs 50% for no Combo. Dropping the cost from 2 uses to 1 changes almost nothing after level 1 (uses never run out in a 4 to 5 round fight). Adding both rolls and letting the target defend once gains only 3 to 4 points and needs a damage-only special case. A Combo the target can't defend against was rejected because enemy Combos use the same rules and it would hit the players. Single-target stays a story-moment pick; area Combos (65 to 72%) are the tactical one.
- **Combos without an attack** (heal + buff, damage + debuff): as written they lose 5 to 8 points (heal + buff) because free BAP does nothing for a heal or a buff. **Decision (Jason, Nov 10):** a Combo heal adds your BAP, and a Combo buff or debuff counts one step higher on the buff table (+4 max). With a 1-use cost that brings heal + buff Combos to even (36 / 50 / 48 / 55 / 60% vs 36 / 51 / 48 / 56 / 61% with no Combo).
- **Decision (Jason, Nov 10): every Combo costs 1 use each** (was 2). Same as any spell or technique. The real price is the held action and once per encounter. Triple Combo: 1 use each too (was 3), Jason confirmed.
- **Not adopted:** auto-landing debuffs, an extra heal that ignores the once-per-person limit, a second fire per encounter, and one defense roll for single-target Combos.
- Sim caveat: damage + debuff Combos stayed about 5 to 9 points behind because the Combo is single-target while the baseline casters use area attacks; that is the same single-target gap above, not a debuff problem.

### Healing changed (Nov 10, 2026; sim19 variant)
Jason: with die-only heals, anyone can heal and the Intellect stat stopped mattering. Sim (same party with a healer vs the 4th member attacking, 4v4 / 4v5): die-only healing was worse than having no healer (hard fights 27% vs 33% at L3), because the heal die is flat while DP grows (a heal restores about 44% of max DP at L1, 32% at L7). Die + stat helps (4v4: 42 / 57 / 53 / 61 / 65% at L1 / 3 / 5 / 7 / 9); die + stat + Edge helps most at higher levels (42 / 57 / 56 / 64 / 69%).
- **Decision (Jason, Nov 10):** heals match every other spell: spell die + stat + Edge. **One heal per person per encounter stays.** Summons that heal roll the same way.
- Combos: because a heal is now a normal roll, a Combo's free BAP applies to it. The attack-less Combo line now only adds: buff or debuff one step up.
- Updated in Core, Kids Core, both SW Guides, the Quick Reference, and the app audit.

### Summons changed (Nov 10, 2026; sim14)
- **Upkeep is now a use, not DP.** Each round a summon acts costs 1 of the caster's uses and that is also its upkeep (no -1 DP per round). When the caster is out of uses, the summon fades. Sim (4 with a Summoner vs 4 plain): 53 / 52 / 53 / 54 / 59% at L1 / 3 / 5 / 7 / 9, within a point of the old -1 DP version. Two uses per round (upkeep plus action) was too costly at L1 to L3 (46 / 45%).
- **Summons are not always magic** (Jason): "temporary creatures, constructs, objects, or whatever else you can imagine"; example: a spirit, or a gooey slime in a test tube. They roll with the stat you use for that spell or technique, not always Intellect.
- Supersedes the earlier "-1 DP per round upkeep" lines above. Updated in Core and Kids Core.

### Jason's read-through (Nov 10, 2026)
Jason read every line Claude had written or reworded, one by one, and rewrote or approved each. Changes beyond the sections above:
- **Ties:** "the tie goes to the defender. (In combat, a tie would be 0 damage.)"
- **Secondary effects:** merged into one paragraph; "area of effect (AOE) ability".
- **Area attacks:** "The attacker rolls once..." in his wording; allies "included for damage"; debuffs "each target rolling their defense".
- **Buff and debuff duration (rewritten, four short paragraphs):** you cast on your turn (casting takes it), you get one action with it on your next turn, and it ends at the start of your turn after that. SW Guide and Quick Reference match.
- **Allies in Combos:** "the same way your main characters can"; Combo part split into its own paragraph.
- **Summons:** "temporary creatures, constructs, objects, or whatever else you can imagine" (example: a spirit, or a gooey slime in a test tube); roll with the stat you use for that spell or technique.
- **Vehicles:** the "vehicle or rider" rule only applies to **open** vehicles ("meaning you can see the rider to attack them directly"). Disabling a Vehicle got two examples (a tire, an engine; Kids: skateboard and rocket scooter).
- **Common effects (SW Guide):** not a menu players ask from; they are what buffs and debuffs look like. A BAP moment the SW awards BAP for can also earn a **BAP effect**: +1 or -1 for 1 round, SW picks the stat, same one-per-stat rule.
- **Damage Effects** is the name for poison, burning, bleeding, etc. everywhere. They can take you to 0 or below, even to -10 and The Calling (Jason: "that's the risk").
- Kept as written: Combo cost table and Triple Combo cost, Risk vs Reward, potions, hazard Resisting, Tethers, unmanned-ship Edge rule, the poison paragraph, the +4 buff cap (Jason: "just leave it").

### Full audit fixes (Nov 16, 2026; audit in claude/tba-full-audit-nov16.md)
Jason asked for a full contradiction and Adult/Kids language audit, then said to apply the fixes.
- **Kids wording:** PDF titles now say "Tools for Being Awesome" (were "Tools for the Bad-Ass: Kids..."); Kids QR title "TBA" (was "TBE"); Damage Effects ends at "The Challenge" (was "The Calling"); "throw a pie" (was beer); playtest sheet "Scarred, not out for good" and summon "is gone after 1 hit"; "getting knocked out constantly"; "No, you can't do that"; weapon flavor "rapid-fire blaster / long-range laser" (was machine gun / sniper rifle); Grief Tether "your friend" (was "the fallen" / "slain"); Memory Echo "a hero's weapon", "where Marcus made his stand."
- **Combos without an attack** reworded (it contradicted itself): a buff or debuff is a flat number, so BAP does nothing for it; it counts one step higher instead (+4 max). A heal is a normal roll and gets BAP. Added to both SW Guides and the Quick References (QR also now says both partners add BAP automatically).
- **BAP on multi-die weapons:** "flat bonuses apply to each die" now says BAP is the exception (one die).
- **Vehicles (SW):** Captain/Pilot "add to attack OR defense" (not "buff"); unmanned stations don't function "except defense."
- **Smaller:** "Weapon dice start at 1d4 and grow... up to 1d12 or a multi-die option"; merged the duplicate magic/upgraded weapons sections into Combat; "Called count" (was "death counter"); "rack up Marks" (was deaths); Hard difficulty "a healer tips it your way" (dropped the stale 65%); Emptiness "(up to -3)" in Adult SW; BAP effect "1 round (until the start of your next turn)."
- **Left for Jason:** Combo effects on the same stat ("newer replaces older" when both fire at once); Marked by Death "loses 1 max DP" vs "becomes a Tether"; Kids "your call" items (trauma, bleeding, knocked out vs knocked out for good, dying wish / final words); character sheet "Healed this encounter" box; archetype pop-culture names.

### Audit follow-ups (Nov 16, 2026, Jason)
- **Combo, both effects on the same stat:** the stronger one takes over (replaces "newer replaces older," which made no sense when both fire at once).
- **Marked by Death / Battle Scarred (option A):** a scar or fear becomes a Tether; a limitation (like not being able to use one technique) just stays with you. Dropped "loses 1 max DP."
- **Kids wording:** "knocked out for good" is now "out of the adventure" everywhere; "trauma" became "fear" / "tough memories"; "bleeding" became "freezing" in Damage Effects; "dying wish" became "last wish"; the final-words prompt is now "If this is goodbye, what do you want to say?"
- **Character sheets:** new "Healed this encounter" checkbox (fillable field healed_this_encounter) in the DP panel, Adult and Kids.
- **Archetypes (sold on itch.io pay-what-you-want):** removed every Pop Culture Examples / Examples line, replaced borrowed quotes with original lines, renamed The Mad Titan to The Cosmic Tyrant, "spider-sense" became "a tingly danger sense", "repulsor" became "hand blaster", and Mario power-ups became generic ones. Titles stay (generic descriptions).

### v3.1 released (Nov 16, 2026)
Jason: "We can tweak it all day but I really need to get it going."
- "DRAFT" removed from every cover, header, footer and file title. Files are now "...v3.1.pdf".
- Core Leveling chapter: the big leveling table moved to the end of the chapter, so the half-empty page after "What You Gain" is gone (57 pages, was 58).
- Release bundles: TBA-v3.1-Tools-for-the-Bad-Ass.zip and TBA-v3.1-Tools-for-Being-Awesome-Kids.zip (Core, SW Guide, QR, fillable character sheets, archetypes, leveling and rules tables; designed and printer-friendly). The playtest sheets stay out of the public bundle.
- Drive: the old folder is renamed "TBA v3.1 (Draft archive)"; the new folder "TBA v3.1 (Release)" holds the playtest sheets.
- Parked for v3.2: Kids layout (bigger type, art), diagrams for the Combo hold and contested rolls, untested Combo pairings (damage + buff, heal + debuff), Damage Effects at level 9, an item bonus cap.

### Adventures updated to v3.1 (Nov 16, 2026)
Jason asked to update the six v3.0 quick-start adventures (Station Theta, The Missing Caravan, The Vanishing; Kids: Space Camp Sabotage, The Dragon's Lost Egg, Detention Dimension).
- Pre-gens: level 2 numbers (10 DP, Edge +1, BAP +1, 4 uses, 1d4 weapon and Defense Die, 1d6 first slot). Each ability is labeled attack, heal, buff, or debuff. Fixed builds that broke the 1/2/3 rule (Thorne, Casey) and 1d6 weapons at level 2 (Detention Dimension).
- Enemies: rebuilt from the leveling tables (DP, Edge, dice) with stats 1/2/3, plus a threat note for 3, 4, or 5 players. Station Theta and The Vanishing each lost one enemy at 4 players (they were Deadly).
- Rules language: The Calling and The Challenge at -10 (was -5); a clean return comes back at 1 DP; hazards use the Environmental Damage tiers and resist-for-half; cover is +1 defense; "disadvantage" and "surprise round" became -1 and "acts first"; heals note the once-per-person limit.
- Kids: Ember is a Pet-style companion (once per fight, -1 to one enemy) instead of a 10 DP Ally; Aurelia's amulet is a once-per-session +1 item (was +1 Edge permanently); the teamwork rules are +1 for helping and BAP for great team moments (was +2 and +1 damage).
- Names: "NASA Youth Space Camp" became "Junior Astronaut Star Camp" and the adventure is now "Star Camp Sabotage"; "Eagle Scout", "YouTuber", "Kevlar", and "Taser" became generic.
- Sources live in /home/claude/adventures/*.md; built with book/adv.py. Added to TBA-v3.1-Complete.zip under "2 Story Weaver Documents/Adventures".
