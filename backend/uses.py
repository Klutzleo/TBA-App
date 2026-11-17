"""
Uses per encounter: ONE shared pool per character (rules v3.1).

Every spell, technique, summon call and Combo spends from the character's pool, no matter which ability it is.
The pool lives on the Character row: max_uses_per_encounter (the size, level + 2) and current_uses (what is left).
The per-ability max_uses / uses_remaining columns still exist but are no longer read for casting.
"""
from backend.leveling import uses_for_level


def pool_max(char) -> int:
    return char.max_uses_per_encounter or uses_for_level(char.level or 1)


def pool_remaining(char) -> int:
    """Uses left, always between 0 and the pool size."""
    mx = pool_max(char)
    cur = char.current_uses
    return mx if cur is None else max(0, min(int(cur), mx))


def spend(char, n: int = 1) -> int:
    """Spend n uses (never below 0). Returns what is left. The caller commits."""
    char.current_uses = max(0, pool_remaining(char) - n)
    return char.current_uses


def refill(char) -> int:
    """Back to a full pool (end of encounter, level change, SW restore)."""
    char.current_uses = pool_max(char)
    return char.current_uses


def restore(char, amount: int) -> int:
    """Give back `amount` uses, capped at the pool size. Returns the new remaining."""
    char.current_uses = min(pool_max(char), pool_remaining(char) + max(0, int(amount)))
    return char.current_uses
