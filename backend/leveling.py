"""
Rules v3.1 leveling numbers, read from schemas/leveling_v3_1.json.

This is the one place the app gets DP, uses per encounter, weapon dice, defense die, Edge and BAP.
Nothing else in the backend should carry its own copy of these tables. The front-end pages still
embed copies (they are plain static files with no build step); tests/test_leveling_tables.py fails
if any of them drift from the JSON.
"""
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas", "leveling_v3_1.json")

with open(_PATH, "r", encoding="utf-8") as _f:
    _DATA = json.load(_f)

MAX_LEVEL = 10  # Ascension (11-15) arrives in a later phase

# {level: {"max_dp", "edge", "bap", "defense_die", "weapon_options", "uses_per_encounter"}}
CHARACTER_LEVELS = {int(k): v for k, v in _DATA["characters"].items()}

# Allies have their own table (rules v3.1): about half the DP, single-die weapons, a first spell from level 1, and they
# stop at level 10. {level: {"max_dp", "edge", "bap", "defense_die", "weapon_options", "uses_per_encounter",
# "slot_1_die", "slot_2_die"}}
ALLY_LEVELS = {int(k): v for k, v in _DATA["allies"].items()}

BUFF_DEBUFF_MODIFIER_BY_DIE = dict(_DATA["buff_debuff"]["modifier_by_die"])
BUFF_DEBUFF_DURATION_ROUNDS = int(_DATA["buff_debuff"]["duration_rounds"])


def level_stats(level: int) -> dict:
    """The full row for a level. Raises ValueError outside 1-MAX_LEVEL."""
    if level not in CHARACTER_LEVELS:
        raise ValueError(f"Level must be 1-{MAX_LEVEL}, got {level}")
    return CHARACTER_LEVELS[level]


def uses_for_level(level: int) -> int:
    """Uses per encounter: level + 2. Out-of-range levels are clamped so a bad row never raises here."""
    level = max(1, min(int(level or 1), MAX_LEVEL))
    return CHARACTER_LEVELS[level]["uses_per_encounter"]


def weapon_options(level: int) -> list:
    return list(level_stats(level)["weapon_options"])


_BUFF_STEPS = ["1d6", "1d8", "1d10", "1d12", "2d6", "2d8"]


def combo_step_modifier(die: str) -> int:
    """A buff or debuff made in a Combo counts one step higher on the buff table (rules v3.1), capped at the top of the
    table (+4). Example: a 1d6 spell is +1 on its own and +2 in a Combo; a 2d8 spell stays at +4."""
    if die not in _BUFF_STEPS:
        return BUFF_DEBUFF_MODIFIER_BY_DIE.get(die, 1)
    nxt = _BUFF_STEPS[min(_BUFF_STEPS.index(die) + 1, len(_BUFF_STEPS) - 1)]
    return min(4, BUFF_DEBUFF_MODIFIER_BY_DIE[nxt])


def ally_stats(level: int) -> dict:
    """The Ally row for a level. Raises ValueError outside 1-10 (Allies stop at level 10)."""
    if level not in ALLY_LEVELS:
        raise ValueError(f"An Ally's level must be 1-{MAX_LEVEL}, got {level}")
    return ALLY_LEVELS[level]


def ally_weapon_options(level: int) -> list:
    return list(ally_stats(level)["weapon_options"])
