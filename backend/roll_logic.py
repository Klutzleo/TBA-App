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