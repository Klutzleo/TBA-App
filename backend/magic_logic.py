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