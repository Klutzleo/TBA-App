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