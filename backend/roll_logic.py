# roll_logic.py

import random
import re
from schemas.loader import CORE_RULESET
from backend.combat_utils import resolve_initiative


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

# Simulates 1v1 Combat
def simulate_combat(attacker, defender, weapon_die, defense_die, bap):
    print("✅ simulate_combat() was called")
    
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
            round_log = {"round": i, "actions": []}

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

                round_log["actions"].append(result)

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
            "final_outcome": outcome
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
                calling_result = resolve_calling(target)
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

def resolve_calling(actor):
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
        actor["echoes"] = actor.get("echoes", []) + [f"{actor['name']} fell in round memory."]
        return f"{actor['name']} fails The Calling—memory echoes in the aftermath."