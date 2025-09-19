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
    level = str(actor["level"])
    stat_key = actor["stat"]
    stat_value = actor.get(stat_key, 0)

    lvl_data = CORE_RULESET["character_leveling"].get(level, {})
    edge = lvl_data.get("Edge", 0)
    bap = lvl_data.get("BAP", 0) if bap_triggered else 0

    actor_die_str = CORE_RULESET["skill_roll"]["actor_die"]
    actor_rolls = roll_dice(actor_die_str)
    actor_die = actor_rolls[0]

    actor_total = actor_die + stat_value + edge + bap

    difficulty_die = difficulty_die or CORE_RULESET["skill_roll"]["opponent_default"]
    opponent_total = sum(roll_dice(difficulty_die))

    crit_val = CORE_RULESET["skill_roll"]["crit_value"]
    fail_val = CORE_RULESET["skill_roll"]["fail_value"]
    outcomes = CORE_RULESET["skill_roll"]["outcomes"]

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
        "narrative": outcomes[outcome],
        "details": {
            "die": actor_die,
            "stat": stat_value,
            "edge": edge,
            "bap": bap
        }
    }