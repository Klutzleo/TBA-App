from backend.effect_registry import EFFECTS
from routes.effects import custom_effects

def simulate_effect(actor, effect, modifiers=None, context=None):
    definition = custom_effects.get(effect) or EFFECTS.get(effect)
    if not definition:
        return {"error": f"Unknown effect: {effect}"}, None

    mod_bonus = sum(modifiers.values()) if modifiers else 0
    damage = definition["base"] + mod_bonus

    outcome = {
        "HP_change": -damage if definition["type"] == "damage" else damage,
        "status": definition["status"],
        "area_damage": definition["area"]
    }

    narration = definition["narration"].format(actor=actor, damage=abs(damage))
    return outcome, narration