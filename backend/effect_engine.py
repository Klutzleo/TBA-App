from models.effect_log import EffectLog
from backend.db import SessionLocal
import uuid

def resolve_effect(actor, effect, source=None, modifiers=None, context=None):
    outcome, narration = simulate_effect(actor, effect, modifiers, context)
    effect_id = str(uuid.uuid4())

    log = EffectLog(
        id=effect_id,
        actor=actor,
        effect=effect,
        source=source,
        hp_change=outcome["HP_change"],
        status=outcome["status"],
        area_damage=outcome["area_damage"],
        narration=narration
    )

    db = SessionLocal()
    db.add(log)
    db.commit()
    db.close()

    return {
        "actor": actor,
        "applied_effect": effect,
        "outcome": outcome,
        "effect_id": effect_id,
        "narration": narration
    }

def simulate_effect(actor, effect, modifiers=None, context=None):
    return {
        "actor": actor,
        "effect": effect,
        "modifiers": modifiers or {},
        "context": context,
        "outcome": "simulated"
    }