"""
Ascension secondary effects (rules v3.1, levels 11 to 15).

At each Ascension level the next ability in slot order gains a secondary effect: slot 1 at level 11, slot 2 at level 12, up to
slot 5 at level 15. The core mechanic does not change (same dice, same roll, same damage or healing). The effect is one use, one
activation: it costs nothing extra and needs no second roll. A debuff secondary effect lands automatically on a hit, and a new
one on the same stat replaces the old. Secondary effects never deal damage on their own.

Stored on the ability as JSON: {"kind": "debuff" | "buff" | "note", "stat": "pp" | "ip" | "sp", "strength": 1-4, "note": text}.
A "cleanse" removes one debuff from whoever the ability helped (a healing ability that also cleanses a debuff); its stat is optional (blank
removes the strongest debuff). A "note" has no automation: the Story Weaver applies it by hand.
"""
SECONDARY_KINDS = ("debuff", "buff", "cleanse", "note")


def secondary_unlock_level(slot) -> int:
    """The level at which this slot gains its secondary effect: 11 for slot 1 up to 15 for slot 5."""
    return 10 + int(slot)


def secondary_unlocked(character_level, slot) -> bool:
    return (character_level or 0) >= secondary_unlock_level(slot)


def normalize_secondary(raw):
    """Validate and clean a secondary effect. Returns the stored dict, or None to clear it. Raises ValueError if invalid."""
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise ValueError("secondary_effect must be an object")
    kind = (raw.get("kind") or "").lower()
    if kind not in SECONDARY_KINDS:
        raise ValueError("kind must be debuff, buff or note")
    note = str(raw.get("note") or "").strip()[:300]
    if kind == "note":
        if not note:
            raise ValueError("A note-only effect needs a note")
        return {"kind": "note", "stat": None, "strength": 0, "note": note}
    stat = (raw.get("stat") or "").lower()
    if kind == "cleanse":
        if stat and stat not in ("pp", "ip", "sp"):
            raise ValueError("stat must be pp, ip or sp")
        return {"kind": "cleanse", "stat": stat or None, "strength": 0, "note": note}
    if stat not in ("pp", "ip", "sp"):
        raise ValueError("stat must be pp, ip or sp")
    try:
        strength = int(raw.get("strength", 1))
    except (TypeError, ValueError):
        strength = 1
    return {"kind": kind, "stat": stat, "strength": max(1, min(4, strength)), "note": note}
