def simulate_effect(actor, effect, modifiers=None, context=None):
    # TODO: Pull effect definition from registry or database
    base_damage = 10 if effect == "fireball" else 5
    mod_bonus = sum(modifiers.values()) if modifiers else 0
    total_damage = base_damage + mod_bonus

    outcome = {
        "HP_change": -total_damage,
        "status": "burned" if effect == "fireball" else "shaken",
        "area_damage": effect == "fireball"
    }

    narration = f"{actor} casts {effect}, dealing {total_damage} damage and altering the battlefield."
    return outcome, narration

def resolve_effect(actor, effect, source=None, modifiers=None, context=None):
    outcome, narration = simulate_effect(actor, effect, modifiers, context)
    # TODO: Apply outcome to actor state
    # TODO: Log effect to history with unique ID
    effect_id = f"{actor}-{effect}-e{hash(str(outcome)) % 10000}"
    return {
        "actor": actor,
        "applied_effect": effect,
        "outcome": outcome,
        "effect_id": effect_id,
        "narration": narration
    }

def undo_effect(actor, effect_id, reason=None):
    # TODO: Lookup effect history and reverse changes
    rollback_successful = True
    narration = f"{actor} rewinds the effect {effect_id}, restoring balance."
    return {
        "actor": actor,
        "undone_effect": effect_id,
        "rollback_successful": rollback_successful,
        "narration": narration
    }