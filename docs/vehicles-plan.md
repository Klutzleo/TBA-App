# Vehicles plan (rules v3.1.1)

Status: decisions made 2026-11-18, building V1 to V3 first (V4, V5 after play). Drafted 2026-11-18 from `Rulebook.md` (Vehicles chapter), the Story Weaver Guide
"Vehicle Combat", and `docs/TBA-App-v3.1.1-Handoff/notes/decisions.md` (Nov 5 and Nov 9 vehicle entries).

## The rules in one screen

- A vehicle uses the Vehicle Leveling Table: DP = the PC row (8 at L1, +2 per level), Edge 1 to 10, its own weapon die, defense die,
  up to five systems (spells/techniques), uses per encounter = level + 2, **one pool shared by every system**. Size is story, not stats.
- **Whoever operates it uses the vehicle's Edge instead of their own.** Their stats (PP/IP/SP) still count.
- **Single pilot** (bike, fighter, mech): attack = vehicle weapon die + PP + vehicle Edge. Defense = vehicle defense die + PP + vehicle Edge.
  Maneuver = 1d6 + PP + vehicle Edge. Damage goes to the vehicle's DP.
- **Multi-crew** (ships): each crew member acts on their own initiative and does their station's job.
  Gunner: weapon die + PP + Edge (the attack). Defense Officer: defense die + PP + Edge (the ship's defense).
  Captain: 1d6 + SP + Edge, added to the Gunner's OR Defense Officer's next roll (their choice). Pilot: 1d6 + IP + Edge, same.
  Engineer: 1d6 + IP + Edge, restores that much DP to the ship. A station with nobody in it does nothing that round,
  except that an unmanned defense still defends with the defense die + vehicle Edge (no character stat).
  Captain/Pilot adds are one-time adds to a roll. They are not buffs and use no buff slot.
- **Systems** work like spells: crew activate them on their turn using their stat + the vehicle's spell die, buff/debuff rules apply,
  uses come out of the vehicle's shared pool.
- **Damage:** to the vehicle DP, not the crew. 0 DP = disabled. At -10 or worse = critical, the SW decides what happens. No Calling for vehicles.
  Open vehicles (bike, horse): the attacker chooses vehicle or rider. Enclosed (ship, tank, mech): crew only hurt on a hull breach the SW rules.
- **Disabling** (sabotage, hacking, called shot): an attack roll against the vehicle's defense. On a hit the SW picks one system or the movement,
  knocked out 2 rounds, no DP cost. An Engineer can restore it early if the SW allows.

## What the app has today

Nothing. No code, table or UI mentions vehicles. The pieces we can reuse:

| Need | Reuse |
|---|---|
| A thing with DP, Edge, dice, abilities, a uses pool | a `Character` row with a flag, exactly like `is_swarm` / `is_summon` |
| Numbers per level | `schemas/leveling_v3_1.json` + `backend/leveling.py` (add a `vehicles` table 1-10; drift tests already guard the front-end copies) |
| Shared uses pool | `backend/uses.py` |
| Systems as abilities | `Ability` rows on the vehicle; casting in `handle_ability_cast` |
| "Knocked out for 2 rounds" | `backend/buffs.py` round ticking (`tick_round`) |
| Attack and defense resolution | `handle_combat_command` (attacker and defender are both looked up by name, defense is rolled automatically) |

## Design

**Data (migration 038, additive only)**
- `characters.is_vehicle BOOLEAN DEFAULT FALSE`, `characters.vehicle_kind` (`open` or `enclosed`, default `enclosed`).
- New table `vehicle_crew` (`vehicle_id`, `character_id`, `station`), unique on (vehicle, station) and on (character) per encounter. Stations:
  `operator` (single pilot), `gunner`, `defense_officer`, `captain`, `pilot`, `engineer`.
- New table `vehicle_crew_adds` (`vehicle_id`, `target` = attack|defense, `amount`, `from_station`, `created_at`): a Captain/Pilot add waiting for the next roll of that kind. Consumed by the next roll, cleared at the end of the encounter.
- A vehicle's `owner` is the campaign (the Story Weaver creates it), not a player. Players take stations.

**Rolls (all through one helper `backend/vehicles.py`)**
- `operator_for(vehicle, station)` returns the crew character or None.
- Attack: the Gunner/Operator attacks as normal, but with the vehicle's weapon die, vehicle Edge and the crew member's PP. Any waiting attack add is consumed.
- Defense: when a vehicle is the defender, it defends with the vehicle defense die + (Defense Officer/Operator PP if manned, else nothing) + vehicle Edge. Any waiting defense add is consumed.
- Captain / Pilot: a station action that rolls and stores an add on the vehicle (their choice attack or defense). Engineer: rolls and restores DP (never above max).
- Maneuver: the existing stat check with Edge swapped to the vehicle's.
- Systems: casting by crew uses the vehicle's Edge and spell die, the crew member's stat, and spends from the vehicle's pool, not theirs.

**Damage and states**
- 0 DP: disabled (cannot attack, defend with die only, no systems). At -10 or worse: "critical" banner to the SW, no Calling. Vehicles are never put into the Calling or marked as unconscious people.
- Open vehicle: attack picker shows the vehicle and its rider as separate targets, so "vehicle or rider" is the attacker's click.
- Disable action (SW or attacker via a called-shot attack): on a hit the SW picks a system or movement, stored as a 2-round effect that ticks down with rounds.

**UI**
- A **Vehicles** bubble beside Add NPC in the Story Weaver's bar; players get a Vehicles button on the Campaign tab (the bar is hidden for them). Not the header.
- SW: Create Vehicle (level from the table, kind open/enclosed, systems), Assign crew, Level up with the party.
- Players: Take station / Leave station, a vehicle card (DP bar, crew, systems, uses), station action buttons.
- Initiative stays per person. The vehicle itself is not in the order.

## Phases (each shipped separately, with tests, like v3.1)

1. **V1 Vehicles exist.** Migration 038, vehicle table in the leveling file, create/edit/level a vehicle, crew assignment, vehicle card. No combat yet.
2. **V2 Single-pilot combat.** Operator attacks and defends with the vehicle's dice and Edge, damage to vehicle DP, 0/-10 states, open-vehicle targeting, maneuver check.
3. **V3 Multi-crew stations.** Gunner, Defense Officer, Captain/Pilot adds, Engineer repair, unmanned-defense rule.
4. **V4 Systems.** Abilities on a vehicle, crew casting with the vehicle Edge and spell die, shared pool, buff/debuff rules.
5. **V5 Disabling and enemy vehicles.** The 2-round knock-out, NPC-crewed vehicles, SW tools, polish.

Every phase: tests first for the rules above, then the code, then a read-through against the Rulebook before it ships.

## Defaults I would pick (change any of these)

- Engineer repair has no once-per-encounter limit (it is a station action, not a spell heal; Jason decided on Nov 9 to leave vehicles as written).
- Heal spells and potions do nothing for a vehicle (same as a summon: it has hits, not hit points of a body). The Engineer and the SW's manual repair are how a vehicle heals.
- A character can hold one station on one vehicle at a time.
- Station stats are the suggested pairings; the SW can override the stat for a roll the way they can for a stat check.
- Vehicle level changes are made by the SW (the rules say they level with the party or by SW grant), not automatically.

## Decisions (Jason, 2026-11-18)

- The Story Weaver creates vehicles and the campaign owns them; players take stations.
- Enemy vehicles are crewed by NPCs assigned to stations, like players.
- Open vehicles: the vehicle and its rider show as separate targets, the attacker picks. No extra prompt.
- First release is V1 to V3. V4 (systems) and V5 (disabling, enemy polish) come after it has been played.

## Not in scope

- Vehicle movement, range or positioning (the rules have none).
- Kids wording (deferred with the rest of Kids mode).
