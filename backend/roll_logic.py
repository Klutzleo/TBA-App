# roll_logic.py

import random
import re
from schemas.loader import CORE_RULESET
from backend.combat_utils import resolve_initiative
from backend.lore_log import add_lore_entry, get_lore_by_round
from backend.utils.storage import store_roll  # adjust path if needed



### 🎲 Dice Utilities ###
def parse_die(die_str):
    match = re.fullmatch(r"(\d+)d(\d+)", die_str)
    if not match:
        raise ValueError(f"Invalid die format: {die_str}")
    return int(match.group(1)), int(match.group(2))

def roll_dice(die_str):
    count, sides = parse_die(die_str)
    return [random.randint(1, sides) for _ in range(count)]

def roll_die(die_str):
    """
    Rolls a single die string like '1d8' and returns the total.
    """
    return sum(roll_dice(die_str))

def max_possible(die_str):
    """
    Returns the maximum possible roll for a given die string.
    """
    count, sides = parse_die(die_str)
    return count * sides

### 🧠 Skill Roll Resolver ###
def resolve_skill_roll(actor, difficulty_die=None, bap_triggered=False):
    try:
        # Extract actor info safely
        level = str(actor.get("level", "1"))
        stat_key = actor.get("stat", "PP")
        stat_value = actor.get(stat_key, 0)

        # Load level data
        lvl_data = CORE_RULESET.get("character_leveling", {}).get(level, {})
        edge = lvl_data.get("Edge", 0)
        bap = lvl_data.get("BAP", 0) if bap_triggered else 0

        # Load skill roll config
        skill_roll = CORE_RULESET.get("skill_roll", {})
        actor_die_str = skill_roll.get("actor_die", "1d6")
        actor_rolls = roll_dice(actor_die_str)
        actor_die = actor_rolls[0]

        actor_total = actor_die + stat_value + edge + bap

        # Opponent roll
        difficulty_die = difficulty_die or skill_roll.get("opponent_default", "1d4")
        opponent_total = sum(roll_dice(difficulty_die))

        # Outcome logic
        crit_val = skill_roll.get("crit_value", 6)
        fail_val = skill_roll.get("fail_value", 1)
        outcomes = skill_roll.get("outcomes", {})

        if actor_die == crit_val:
            outcome = "critical success"
        elif actor_die == fail_val:
            outcome = "critical failure"
        elif actor_total > opponent_total:
            outcome = "success"
        else:
            outcome = "failure"

        return {
            "type": "skill",
            "actor_roll": actor_total,
            "opponent_roll": opponent_total,
            "outcome": outcome,
            "narrative": outcomes.get(outcome, "No narrative available."),
            "details": {
                "die": actor_die,
                "stat": stat_value,
                "edge": edge,
                "bap": bap
            }
        }

    except Exception as e:
        print("Skill roll error:", str(e))
        raise

# Combat rolls

def resolve_combat_roll(attacker, defender, weapon_die, defense_die, bap_triggered=False):
    atk_roll = roll_die(weapon_die)
    def_roll = roll_die(defense_die)
    margin = atk_roll - def_roll

    outcome = "miss" if margin <= 0 else "hit"
    critical = atk_roll == max_possible(weapon_die)

    narrative = generate_combat_narrative(attacker, defender, outcome, margin, critical)

    return {
        "type": "combat",
        "attacker_roll": atk_roll,
        "defender_roll": def_roll,
        "outcome": outcome,
        "narrative": narrative,
        "details": {
            "margin": margin,
            "critical": critical,
            "bap_triggered": bap_triggered
        }
    }

#Fun narrative

def generate_combat_narrative(attacker, defender, outcome, margin, critical):
    name_a = attacker.get("name", "Attacker")
    name_d = defender.get("name", "Defender")

    if outcome == "miss":
        return f"{name_d} deflects the blow from {name_a} with ease."
    if critical:
        return f"{name_a} lands a devastating strike—{name_d} staggers!"
    if margin >= 5:
        return f"{name_a} overwhelms {name_d} with brutal precision."
    return f"{name_a} strikes true, bypassing {name_d}'s defenses."

# Simulates 1v1 Combat
# roll_logic.py

import random
import re
from schemas.loader import CORE_RULESET

### 🎲 Dice Utilities ###
def parse_die(die_str):
    match = re.fullmatch(r"(\d+)d(\d+)", die_str)
    if not match:
        raise ValueError(f"Invalid die format: {die_str}")
    return int(match.group(1)), int(match.group(2))

def roll_dice(die_str):
    count, sides = parse_die(die_str)
    return [random.randint(1, sides) for _ in range(count)]

def roll_die(die_str):
    """
    Rolls a single die string like '1d8' and returns the total.
    """
    return sum(roll_dice(die_str))

def max_possible(die_str):
    """
    Returns the maximum possible roll for a given die string.
    """
    count, sides = parse_die(die_str)
    return count * sides

### 🧠 Skill Roll Resolver ###
def resolve_skill_roll(actor, difficulty_die=None, bap_triggered=False):
    try:
        # Extract actor info safely
        level = str(actor.get("level", "1"))
        stat_key = actor.get("stat", "PP")
        stat_value = actor.get(stat_key, 0)

        # Load level data
        lvl_data = CORE_RULESET.get("character_leveling", {}).get(level, {})
        edge = lvl_data.get("Edge", 0)
        bap = lvl_data.get("BAP", 0) if bap_triggered else 0

        # Load skill roll config
        skill_roll = CORE_RULESET.get("skill_roll", {})
        actor_die_str = skill_roll.get("actor_die", "1d6")
        actor_rolls = roll_dice(actor_die_str)
        actor_die = actor_rolls[0]

        actor_total = actor_die + stat_value + edge + bap

        # Opponent roll
        difficulty_die = difficulty_die or skill_roll.get("opponent_default", "1d4")
        opponent_total = sum(roll_dice(difficulty_die))

        # Outcome logic
        crit_val = skill_roll.get("crit_value", 6)
        fail_val = skill_roll.get("fail_value", 1)
        outcomes = skill_roll.get("outcomes", {})

        if actor_die == crit_val:
            outcome = "critical success"
        elif actor_die == fail_val:
            outcome = "critical failure"
        elif actor_total > opponent_total:
            outcome = "success"
        else:
            outcome = "failure"

        return {
            "type": "skill",
            "actor_roll": actor_total,
            "opponent_roll": opponent_total,
            "outcome": outcome,
            "narrative": outcomes.get(outcome, "No narrative available."),
            "details": {
                "die": actor_die,
                "stat": stat_value,
                "edge": edge,
                "bap": bap
            }
        }

    except Exception as e:
        print("Skill roll error:", str(e))
        raise

# Combat rolls

def resolve_combat_roll(attacker, defender, weapon_die, defense_die, bap_triggered=False):
    atk_roll = roll_die(weapon_die)
    def_roll = roll_die(defense_die)
    margin = atk_roll - def_roll

    outcome = "miss" if margin <= 0 else "hit"
    critical = atk_roll == max_possible(weapon_die)

    narrative = generate_combat_narrative(attacker, defender, outcome, margin, critical)

    return {
        "type": "combat",
        "attacker_roll": atk_roll,
        "defender_roll": def_roll,
        "outcome": outcome,
        "narrative": narrative,
        "details": {
            "margin": margin,
            "critical": critical,
            "bap_triggered": bap_triggered
        }
    }

#Fun narrative

def generate_combat_narrative(attacker, defender, outcome, margin, critical):
    name_a = attacker.get("name", "Attacker")
    name_d = defender.get("name", "Defender")

    if outcome == "miss":
        return f"{name_d} deflects the blow from {name_a} with ease."
    if critical:
        return f"{name_a} lands a devastating strike—{name_d} staggers!"
    if margin >= 5:
        return f"{name_a} overwhelms {name_d} with brutal precision."
    return f"{name_a} strikes true, bypassing {name_d}'s defenses."

# Simulates encounter-based combat with effects, echoes, and lore
def simulate_encounter_combat(attacker, defender, weapon_die, defense_die, bap):
    print("✅ simulate_combat() was called")

    import uuid
    from backend.encounter_memory import set_encounter_id, resolve_effects, get_effects, remove_effect
    from backend.lore_log import add_lore_entry
    
    encounter_id = str(uuid.uuid4())
    set_encounter_id(encounter_id)
    
    # Roll initiative for both combatants
    combatants = [attacker, defender]
    initiative_rolls = roll_initiative(combatants)
    initiative_order = [r["name"] for r in initiative_rolls]

    try:
        attacker_dp = attacker.get("DP", 10)
        defender_dp = defender.get("DP", 10)

        rounds = []
        i = 1
        while True:
            round_log["effects"] = effects
            round_log = {"round": i, "actions": []}
            
            effects = resolve_effects(i)
            for effect in effects:
                echo = {
                    "actor": effect["actor"],
                    "round": i,
                    "tag": effect.get("tag", "effect"),
                    "message": f"{effect['actor']} is affected by {effect['effect']}",
                    "encounter_id": encounter_id
                }
                if effect["tag"] == "poison":
                    if effect["actor"] == attacker["name"]:
                        attacker_dp -= 1
                    elif effect["actor"] == defender["name"]:
                        defender_dp -= 1
                add_lore_entry(echo)
                print(f"🔮 {echo['message']}")

                if effect["duration"] <= 0:
                    remove_effect(effect["actor"], effect.get("tag"))
                    add_lore_entry({
                        "actor": effect["actor"],
                        "round": i,
                        "tag": "expired",
                        "message": f"{effect['tag']} effect on {effect['actor']} has expired.",
                        "encounter_id": encounter_id
                    })

            for effect in get_effects():
                if effect.get("duration"):
                    effect["duration"] -= 1
                    if effect["duration"] <= 0:
                        remove_effect(effect["actor"], effect.get("tag"))


            for actor_name in initiative_order:
                actor = next(c for c in combatants if c["name"] == actor_name)
                target = defender if actor == attacker else attacker

                result = resolve_combat_roll(actor, target, weapon_die, defense_die, bap)
                damage = max(0, result["details"].get("margin", 0))

                # Apply damage
                if target == attacker:
                    attacker_dp -= damage
                else:
                    defender_dp -= damage

                result.update({
                    "attacker": actor.get("name", "Attacker"),
                    "defender": target.get("name", "Defender"),
                    "details": {**result["details"], "damage": damage},
                    "dp": {
                        attacker.get("name", "Attacker"): attacker_dp,
                        defender.get("name", "Defender"): defender_dp
                    }
                })

                    # Store roll in DB
                store_roll(
                    actor=actor.get("name"),
                    target=target.get("name"),
                    roll_type="combat",
                    roll_mode=actor.get("roll_mode", "auto"),
                    triggered_by=actor.get("triggered_by", "unknown"),
                    result=result,
                    modifiers={
                        "edge": actor.get("edge", 0),
                        "bap": actor.get("bap", 0),
                        "emotional_flags": actor.get("emotional_flags", []),
                        "tethers": actor.get("tethers", []),
                        "echoes": actor.get("echoes", [])
                    },
                    session_id=actor.get("session_id"),
                    encounter_id=encounter_id
                )

                round_log["actions"].append(result)

                echo = {
                    "actor": actor.get("name", "Unknown"),
                    "round": i,
                    "tag": actor.get("status", "combat"),
                    "message": result.get("narrative", f"{actor_name} acted in round {i}"),
                    "encounter_id": encounter_id
                }
                add_lore_entry(echo)


                print(f"Round {i} - {actor_name} strikes: {result['narrative']} | DP: {attacker_dp} vs {defender_dp}")

                # Early termination
                if attacker_dp <= 0 or defender_dp <= 0:
                    break

            rounds.append(round_log)

            if attacker_dp <= 0 or defender_dp <= 0:
                break

            i += 1

        # Final outcome
        if attacker_dp > defender_dp:
            outcome = f"{attacker['name']} wins by reducing {defender['name']}'s DP to {defender_dp}"
        elif defender_dp > attacker_dp:
            outcome = f"{defender['name']} wins by reducing {attacker['name']}'s DP to {attacker_dp}"
        else:
            outcome = "Draw"

        summary = f"{attacker['name']} and {defender['name']} clash over {len(rounds)} rounds."

        # Gather lore echoes for each round
        lore_summary = []
        for r in range(1, len(rounds) + 1):
            lore_summary.extend(get_lore_by_round(r))


            battle_log = {
                "type": "combat_simulation",
                "combatants": {
                    "players": [attacker.get("name", "Attacker")],
                    "enemies": [defender.get("name", "Defender")],
                },
                "initiative_order": initiative_order,
                "initiative_rolls": initiative_rolls,
                "start_dp": {
                    attacker.get("name", "Attacker"): attacker.get("current_dp", 10),
                    defender.get("name", "Defender"): defender.get("current_dp", 10)
                },
                "rounds": rounds,
                "round_count": len(rounds),
                "final_dp": {
                    attacker.get("name", "Attacker"): attacker_dp,
                    defender.get("name", "Defender"): defender_dp
                },
                "summary": summary,
                "final_outcome": outcome,
                "lore": lore_summary,
                "encounter_id": encounter_id
            }
            
            return {
                "battle_log": battle_log
            }


    

    except Exception as e:
        print("Simulation error:", str(e))
        raise

def generate_summary(log, attacker, defender):
    last = log[-1]
    if last["details"]["critical"]:
        return f"{attacker['name']} lands a decisive blow—{defender['name']} falls after {last['round']} rounds."
    return f"{attacker['name']} outmaneuvers {defender['name']} over {last['round']} rounds."

def roll_initiative(combatants):
    def score(c):
        roll = roll_die("1d6")
        edge = c.get("stats", {}).get("Edge", 0)
        return {
            "name": c["name"],
            "roll": roll,
            "edge": edge,
            "total": roll + edge,
            "physical": c["stats"].get("PP", 0),
            "intellect": c["stats"].get("IP", 0),
            "social": c["stats"].get("SP", 0)
        }

    rolls = [score(c) for c in combatants]

    # Sort with tiebreakers
    rolls.sort(key=lambda r: (
        -r["total"],
        -r["physical"],
        -r["intellect"],
        -r["social"]
    ))

    return rolls

def check_tether(actor, context):
    active_mods = []
    for tether in actor.get("tethers", []):
        if tether["condition"] in context:
            active_mods.append(tether["modifier"])
    return active_mods

def trigger_echo(actor, context):
    bonuses = []
    for echo in actor.get("echoes", []):
        if echo["trigger"] in context:
            bonuses.append(echo["effect"])
    return bonuses

from routes.lore import add_lore_entry  # make sure this is imported

def resolve_calling(actor, round_num=None, encounter_id=None):
    ip = actor["stats"].get("IP", 0)
    sp = actor["stats"].get("SP", 0)
    sw_roll = roll_die("1d6")

    ip_success = ip >= sw_roll
    sp_success = sp >= sw_roll

    if ip_success or sp_success:
        actor["dp"] = -4
        actor["marked_by_death"] = True
        return f"{actor['name']} resists The Calling—marked, but not gone."
    else:
        actor["dp"] = -6
        echo = {
            "moment": "The Calling",
            "round": round_num,
            "description": f"{actor['name']} fell in round memory.",
            "effect": "+1d6 to allies when avenging",
            "trigger": "avenging",
            "location": actor.get("location", "Unknown")
        }
        actor["echoes"] = actor.get("echoes", []) + [echo]

        # ✅ Log to lore before returning
        lore_entry = {
            "actor": actor["name"],
            "moment": "The Calling",
            "description": echo["description"],
            "effect": echo["effect"],
            "location": echo["location"],
            "round": round_num,
            "encounter_id": encounter_id
        }
        add_lore_entry(lore_entry)

        return f"{actor['name']} fails The Calling—memory echoes in the aftermath."
    
    

def simulate_encounter(actors, rounds=3, log=True, encounter_id=None):
    initiative_order = resolve_initiative(actors)
    combat_log = [f"Initiative order: {', '.join(initiative_order)}"]
    round_results = []

    # Initialize DP for all actors
    for actor in actors:
        actor["dp"] = actor.get("dp", 10)

    for r in range(rounds):
        round_log = [f"Round {r+1} begins"]
        for name in initiative_order:
            actor = next(a for a in actors if a["name"] == name)
            if actor["dp"] <= -5:
                round_log.append(f"{actor['name']} is unconscious or in The Calling.")
                continue

            # Choose a target (round-robin or random)
            targets = [a for a in actors if a["name"] != name and a["dp"] > -5]
            if not targets:
                round_log.append(f"{actor['name']} has no valid targets.")
                continue
            target = random.choice(targets)

            # 🧷 Check for tether activation
            context = f"{actor['name']} vs {target['name']}"
            modifiers = check_tether(actor, context)

            # Base attack total
            atk_total = actor["stats"].get("PP", 0) + actor.get("edge", 0)

            # Apply tether modifiers
            for mod in modifiers:
                atk_total += roll_die(mod)

            if modifiers:
                round_log.append(f"{actor['name']}'s tether activates: {', '.join(modifiers)}")

            # Apply echo bonuses
            echo_bonuses = trigger_echo(actor, context)
            for bonus in echo_bonuses:
                atk_total += roll_die(bonus)
            if echo_bonuses:
                round_log.append(f"{actor['name']} is moved by memory: {', '.join(echo_bonuses)}")

            # Resolve combat (PP + Edge vs PP + Edge)
            def_total = target["stats"].get("PP", 0) + target.get("edge", 0)
            margin = atk_total - def_total

            if margin > 0:
                target["dp"] -= margin
                round_log.append(f"{actor['name']} hits {target['name']} for {margin} damage.")
            else:
                round_log.append(f"{actor['name']} misses {target['name']}.")

            # Death threshold check
            if target["dp"] <= -5:
                round_log.append(f"{target['name']} enters The Calling...")

            if target["dp"] <= -5 and not target.get("marked_by_death"):
                calling_result = resolve_calling(target, round_num=r+1, encounter_id=encounter_id)
                round_log.append(calling_result)

        round_results.append({"round": r+1, "log": round_log})

        # Early termination if only one actor remains conscious
        alive = [a for a in actors if a["dp"] > -5]
        if len(alive) <= 1:
            break

    summary = {
        "actors": [{ "name": a["name"], "dp": a["dp"] } for a in actors],
        "survivors": [a["name"] for a in actors if a["dp"] > -5],
        "fallen": [a["name"] for a in actors if a["dp"] <= -5]
    }

    return {
        "rounds": round_results,
        "outcome": "simulation complete",
        "log": combat_log,
        "summary": summary
    }


# Backwards-compatible wrapper expected by some routes
def simulate_combat(*args, **kwargs):
    """Compatibility shim: delegates to `simulate_encounter` or
    `simulate_encounter_combat` depending on provided args.
    """
    # If caller provided a list of actors, delegate to simulate_encounter
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        actors = args[0]
        rounds = kwargs.get("rounds", 3)
        return simulate_encounter(actors, rounds=rounds, encounter_id=kwargs.get("encounter_id"))

    # If called with attacker/defender, delegate to single-encounter sim
    if len(args) >= 2 or ("attacker" in kwargs and "defender" in kwargs):
        # normalize positional or kw form
        if len(args) >= 2:
            attacker = args[0]
            defender = args[1]
            weapon_die = args[2] if len(args) > 2 else kwargs.get("weapon_die")
            defense_die = args[3] if len(args) > 3 else kwargs.get("defense_die")
            bap = args[4] if len(args) > 4 else kwargs.get("bap", False)
        else:
            attacker = kwargs.get("attacker")
            defender = kwargs.get("defender")
            weapon_die = kwargs.get("weapon_die")
            defense_die = kwargs.get("defense_die")
            bap = kwargs.get("bap", False)
        return simulate_encounter_combat(attacker, defender, weapon_die, defense_die, bap)

    raise ValueError("simulate_combat requires either an actors list or attacker and defender")

# ...existing code...

def resolve_multi_die_attack(
    attacker,
    attacker_die_str,
    attacker_stat_value,
    defender,
    defense_die_str,
    defender_stat_value,
    edge,
    bap_triggered=False,
    weapon_bonus=0
):
    """
    TBA v1.5 Multi-Die Attack Resolution.
    
    Attacker rolls each die individually against defender's single defense die.
    Each roll generates its own margin and damage.
    
    Args:
        attacker: dict with "name" key
        attacker_die_str: e.g., "3d4", "2d6", "1d8"
        attacker_stat_value: PP/IP/SP (1-3)
        defender: dict with "name" key
        defense_die_str: e.g., "1d8"
        defender_stat_value: PP/IP/SP (1-3)
        edge: bonus from level (0-5)
        bap_triggered: bool, adds BAP bonus to each roll
        weapon_bonus: bonus to damage per roll (Phase 2, default 0)
    
    Returns:
        {
            "type": "multi_die_attack",
            "attacker_name": str,
            "defender_name": str,
            "individual_rolls": [
                {"attacker_roll": int, "defense_roll": int, "margin": int, "damage": int},
                ...
            ],
            "total_damage": int,
            "outcome": "hit" | "miss" | "partial_hit",
            "narrative": str,
            "details": {
                "attacker_die_str": str,
                "defense_die_str": str,
                "attacker_stat": int,
                "defender_stat": int,
                "edge": int,
                "bap_triggered": bool,
                "weapon_bonus": int,
                "hit_count": int,
                "total_rolls": int
            }
        }
    """
    attacker_name = attacker.get("name", "Attacker")
    defender_name = defender.get("name", "Defender")
    
    # Parse attacker die string (e.g., "3d4" → count=3, sides=4)
    attacker_count, attacker_sides = parse_die(attacker_die_str)
    
    # Roll each attacker die separately
    attacker_rolls = roll_dice(attacker_die_str)  # Returns list of individual rolls
    
    # Roll defense die once (same for all attacker rolls)
    defense_roll = roll_die(defense_die_str)
    
    # Calculate individual results
    individual_rolls = []
    total_damage = 0
    hit_count = 0
    
    for atk_die_roll in attacker_rolls:
        # Margin = attacker die - defense die
        margin = atk_die_roll - defense_roll
        
        # Damage: margin if positive, else 0
        # Phase 2: weapon_bonus would apply here
        damage = max(0, margin) + weapon_bonus
        
        if margin > 0:
            hit_count += 1
        
        total_damage += damage
        
        individual_rolls.append({
            "attacker_roll": atk_die_roll,
            "defense_roll": defense_roll,
            "margin": margin,
            "damage": damage
        })
    
    # Determine outcome
    if hit_count == 0:
        outcome = "miss"
    elif hit_count == len(attacker_rolls):
        outcome = "hit"
    else:
        outcome = "partial_hit"
    
    # Generate narrative
    narrative = generate_multi_die_narrative(
        attacker_name,
        defender_name,
        outcome,
        hit_count,
        len(attacker_rolls),
        total_damage
    )
    
    return {
        "type": "multi_die_attack",
        "attacker_name": attacker_name,
        "defender_name": defender_name,
        "individual_rolls": individual_rolls,
        "total_damage": total_damage,
        "outcome": outcome,
        "narrative": narrative,
        "details": {
            "attacker_die_str": attacker_die_str,
            "defense_die_str": defense_die_str,
            "attacker_stat": attacker_stat_value,
            "defender_stat": defender_stat_value,
            "edge": edge,
            "bap_triggered": bap_triggered,
            "weapon_bonus": weapon_bonus,
            "hit_count": hit_count,
            "total_rolls": len(attacker_rolls)
        }
    }


def generate_multi_die_narrative(attacker_name, defender_name, outcome, hits, total_rolls, total_damage):
    """
    Generate narrative for multi-die attack.
    
    Args:
        attacker_name: str
        defender_name: str
        outcome: "hit" | "miss" | "partial_hit"
        hits: number of successful rolls
        total_rolls: total number of rolls
        total_damage: total damage dealt
    
    Returns:
        str: narrative description
    """
    hit_rate = f"{hits}/{total_rolls}"
    
    if outcome == "miss":
        return f"{defender_name} expertly deflects all {total_rolls} strikes from {attacker_name}!"
    elif outcome == "hit":
        return f"{attacker_name} lands all {total_rolls} hits on {defender_name}—{total_damage} damage!"
    else:  # partial_hit
        return f"{attacker_name} connects with {hit_rate} strikes on {defender_name}—{total_damage} damage total."