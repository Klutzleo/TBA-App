# server/backend/magic_logic.py

import random
from typing import List, Dict
from backend.encounter_memory import get_effects, remove_effect

def get_spell_die(level, slot):
    spell_table = {
        1: ["1d6", None, None, None, None],
        3: ["1d8", "1d6", None, None, None],
        5: ["1d10", "1d8", "1d6", None, None],
        7: ["1d12", "1d10", "1d8", "1d8", None],
        9: ["2d8", "1d12", "1d10", "1d10", "1d10"],
        10: ["2d8", "1d12", "2d6", "1d10", "1d12"]
    }
    for lvl in sorted(spell_table.keys(), reverse=True):
        if level >= lvl:
            return spell_table[lvl][slot]
    return "1d6"  # fallback

def roll_die(die: str) -> int:
    count, faces = map(int, die.lower().split("d"))
    return sum(random.randint(1, faces) for _ in range(count))

class Spell:
    def __init__(self, slot: int, die: str, name: str = None):
        self.slot = slot
        self.die = die
        self.name = name or f"Spell {slot}"
        self.is_aoe = slot in (2, 4)

class Character:
    def __init__(self, name: str, stats: Dict[str, int], edge: int,
                 defense_die: str, bap: int, spells: Dict[int, Spell]):
        self.name = name
        self.level = stats.get("level", 1)
        self.stats = stats
        self.edge = edge
        self.defense_die = defense_die
        self.bap = bap
        self.spellbook = spells
        self._casts = {slot: 0 for slot in spells}
        self.marked_by_death = False

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

class Spell:
    def __init__(self, slot, traits=None, bap_triggered=False, name=None):
        self.slot = slot
        self.traits = traits or []
        self.bap_triggered = bap_triggered
        self.name = name or "Unnamed Spell"

def spell_from_dict(data):
    return Spell(
        slot=data["slot"],
        traits=data.get("traits", []),
        bap_triggered=data.get("bap_triggered", False),
        name=data.get("name", "Unnamed Spell")
    )

def resolve_spellcast(caster, target, spell, distance="medium", log=False, encounter_id=None):
    # Convert dicts to Character objects
    caster = character_from_dict(caster)
    target = character_from_dict(target)
    spell = spell_from_dict(spell)

    # Determine spell die from level and slot
    spell_die = get_spell_die(caster.level, spell.slot)  # e.g., "1d8"

    buff_table = {
    "1d6": 1, "1d8": 2, "1d10": 3, "1d12": 4, "2d6": 5, "2d8": 6
    }
    
    spell_roll = roll_die(spell_die) + caster.stats["IP"] + caster.edge + modifier
    defense_roll = roll_die(target.defense_die) + target.stats["PP"] + target.edge
    bap_triggered = spell.bap_triggered

    # Calculate damage
    damage = max(spell_roll - defense_roll, 0)
    target.current_dp -= damage

    # Trait narration
    effects = []
    notes = []
    notes.append(f"{caster.name} casts {spell.name}!")
    if "burn" in spell.traits and damage > 0:
        effects.append("burn")
        notes.append(f"{target.name} is scorched by flames!")
    if "stun" in spell.traits and damage > 0:
        effects.append("stun")
        notes.append(f"{target.name} is momentarily stunned!")
    if "area" in spell.traits:
        notes.append("The spell affects a wide area.")

    # DP thresholds
    if target.current_dp <= -5:
        notes.append(f"{target.name} has entered The Calling.")
    elif target.current_dp <= -3:
        notes.append(f"{target.name} is severely wounded.")
    elif target.current_dp <= -1:
        notes.append(f"{target.name} is moderately wounded.")

    if target.current_dp <= -5:
        calling_result = resolve_calling(target)
        notes.append(calling_result["note"])

    if hasattr(caster, "tethers"):
        for tether in caster.tethers:
            if tether == "Protect the innocent" and getattr(target, "role", None) == "noncombatant":
                notes.append(f"{caster.name}'s tether activates: +1d8 to shielding roll.")

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

def resolve_calling(character):
    from random import randint

    stat = character.stats.get("IP", 0) or character.stats.get("SP", 0)
    player_roll = randint(1, 6) + stat + character.edge
    sw_roll = randint(1, 6) + 3
    character.marked_by_death = True

    if player_roll >= sw_roll:
        character.current_dp = -4
        return {
            "status": "survived",
            "note": f"{character.name} stabilizes in The Calling and is Marked by Death.",
            "marked_by_death": True
        }
    else:
        return {
            "status": "failed",
            "note": f"{character.name} fades in The Calling. Allies may gain a memory echo.",
            "memory_echo": True
        }

# backend/magic_logic.py

def resolve_effects(round: int):
    active = get_effects()
    results = []

    for effect in active:
        if effect.get("round") == round:
            actor = effect["actor"]
            effect_type = effect["effect"]
            duration = effect["duration"]

            if effect_type == "burn":
                dmg = roll_die("1d4")
                results.append({
                    "actor": actor,
                    "effect": "burn",
                    "damage": dmg,
                    "note": f"{actor} takes {dmg} burn damage at start of round {round}."
                })
            elif effect_type == "buff":
                results.append({
                    "actor": actor,
                    "effect": "buff",
                    "note": f"{actor} gains a temporary bonus from {effect.get('tag')}."
                })

            # Decrement or remove
            if duration <= 1:
                remove_effect(actor, tag=effect.get("tag"))
            else:
                effect["duration"] -= 1

    return results