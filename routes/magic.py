from flask_smorest import Blueprint
from schemas.combat import SpellCastRequest, SpellCastResponse
from flask import request

magic_blp = Blueprint("magic", "magic", url_prefix="/api", description="Magical spellcasting endpoints")

@magic_blp.route("/cast/spell", methods=["POST"])
@magic_blp.arguments(SpellCastRequest)
@magic_blp.response(200, SpellCastResponse)
def cast_spell(payload):
    caster = payload["caster"]
    target = payload["target"]
    spell = payload["spell"]
    distance = payload.get("distance", "medium")
    log_enabled = payload.get("log", False)

    # Basic resolution logic
    caster_power = spell.get("power", 0)
    target_resistance = target["stats"].get("wisdom", 0)
    margin = caster_power - target_resistance
    outcome = "hit" if margin > 0 else "miss"
    effects = spell.get("traits", []) if outcome == "hit" else []

    # Narrative log
    log = []
    if log_enabled:
        log.append(f"{caster['name']} casts {spell['name']} at {target['name']}...")
        log.append(f"Spell power: {caster_power}, Target resistance: {target_resistance}")
        log.append(f"Outcome: {outcome}")
        if effects:
            log.append(f"Effects triggered: {', '.join(effects)}")

    return {
        "outcome": outcome,
        "damage": caster_power if outcome == "hit" else 0,
        "effects": effects,
        "log": log,
        "notes": []
    }