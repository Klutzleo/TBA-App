# server/backend/magic_logic.py

import random
from typing import List, Dict

def roll_die(die: str) -> int:
    count, faces = map(int, die.lower().split("d"))
    return sum(random.randint(1, faces) for _ in range(count))

class Spell:
    def __init__(self, slot: int, die: str):
        self.slot = slot
        self.die = die
        self.is_aoe = slot in (2, 4)

class Character:
    def __init__(self, name: str, stats: Dict[str, int], edge: int,
                 defense_die: str, bap: int, spells: Dict[int, Spell]):
        self.name = name
        self.stats = stats
        self.edge = edge
        self.defense_die = defense_die
        self.bap = bap
        self.spellbook = spells
        self._casts = {slot: 0 for slot in spells}

    def can_cast(self, slot: int) -> bool:
        return self._casts.get(slot, 0) < 3

    def record_cast(self, slot: int):
        self._casts[slot] += 1

    def reset_casts(self):
        for slot in self._casts:
            self._casts[slot] = 0

def cast_spell(
    caster: Character,
    targets: List[Character],
    slot: int,
    bap_triggered: bool = False
) -> Dict:
    assert slot in caster.spellbook, f"Unknown slot {slot}"
    assert caster.can_cast(slot), f"No casts left in slot {slot}"
    spell = caster.spellbook[slot]

    base_roll = roll_die(spell.die) + caster.stats["IP"] + caster.edge
    if bap_triggered:
        base_roll += caster.bap

    entry = {
        "caster": caster.name,
        "slot": slot,
        "roll": base_roll,
        "bap_used": bap_triggered,
        "results": []
    }

    actual_targets = targets if spell.is_aoe else targets[:1]
    for tgt in actual_targets:
        defend = roll_die(tgt.defense_die) + tgt.stats["IP"] + tgt.edge
        damage = max(0, base_roll - defend)
        tgt.current_dp -= damage
        entry["results"].append({
            "target": tgt.name,
            "defend_roll": defend,
            "damage": damage,
            "remaining_dp": tgt.current_dp
        })

    caster.record_cast(slot)
    return entry

def character_from_dict(data: dict) -> Character:
    """
    Build a Character (with spells) from a JSON‐like dict.
    Expects:
      data["name"], data["stats"], data["edge"],
      data["defense_die"], data["bap"],
      data["spells"]: { slot: { "die": "1d6" }, … }
      data["current_dp"]  (optional)
    """
    spells = {
        int(slot): Spell(int(slot), spec["die"])
        for slot, spec in data.get("spells", {}).items()
    }
    char = Character(
        name=data["name"],
        stats=data["stats"],
        edge=data.get("edge", 0),
        defense_die=data.get("defense_die", "1d6"),
        bap=data.get("bap", 0),
        spells=spells
    )
    # set current DP and reset casts
    char.current_dp = data.get("current_dp", data["stats"].get("DP", 0))
    char.reset_casts()
    return char

def resolve_spellcast(caster, target, spell, distance="medium", log=False, encounter_id=None):
    # Convert dicts to Character objects
    caster = character_from_dict(caster)
    target = character_from_dict(target)

    # Determine spell die from level and slot
    spell_slot = 0  # assuming slot 0 for now
    spell_die = get_spell_die(caster.level, slot=spell_slot)  # e.g., "1d8"

    # Roll spell attack
    spell_roll = roll_die(spell_die) + caster.IP + caster.edge

    # Roll target defense
    defense_roll = roll_die(target.defense_die) + target.PP + target.edge

    # Calculate damage
    damage = max(spell_roll - defense_roll, 0)
    target.current_dp -= damage

    # Trait narration
    effects = []
    notes = []
    if "burn" in spell.get("traits", []) and damage > 0:
        effects.append("burn")
        notes.append(f"{target.name} is scorched by flames!")
    if "stun" in spell.get("traits", []) and damage > 0:
        effects.append("stun")
        notes.append(f"{target.name} is momentarily stunned!")
    if "area" in spell.get("traits", []):
        notes.append("The spell affects a wide area.")

    # DP thresholds
    if target.current_dp <= -5:
        notes.append(f"{target.name} has entered The Calling.")
    elif target.current_dp <= -3:
        notes.append(f"{target.name} is severely wounded.")
    elif target.current_dp <= -1:
        notes.append(f"{target.name} is moderately wounded.")

    # Lore logging
    if encounter_id:
        from backend.encounter_memory import add_lore_entry
        for effect in effects:
            add_lore_entry(
                actor=target.name,
                round=None,
                tag="spell",
                effect=effect,
                duration=2,
                encounter_id=encounter_id
            )

    return {
        "outcome": "hit" if damage > 0 else "miss",
        "damage": damage,
        "effects": effects,
        "log": [{
            "target": target.name,
            "spell_roll": spell_roll,
            "defense_roll": defense_roll,
            "damage": damage,
            "remaining_dp": target.current_dp
        }] if log else [],
        "notes": notes
    }