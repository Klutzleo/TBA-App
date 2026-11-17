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
