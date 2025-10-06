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

    # Canonical stat resolution
    caster_ip = caster["stats"].get("IP", 0)
    target_ip = target["stats"].get("IP", 0)
    caster_edge = caster.get("edge", 0)
    target_edge = target.get("edge", 0)

    # Total roll values
    caster_roll = caster_ip + caster_edge
    target_roll = target_ip + target_edge
    margin = caster_roll - target_roll

    # Outcome logic
    outcome = "hit" if margin > 0 else "miss"
    effects = spell.get("traits", []) if outcome == "hit" else []

    # Narrative log
    log = []
    if log_enabled:
        log.append(f"{caster['name']} casts {spell['name']} at {target['name']}...")
        log.append(f"Caster IP + Edge: {caster_ip} + {caster_edge} = {caster_roll}")
        log.append(f"Target IP + Edge: {target_ip} + {target_edge} = {target_roll}")
        log.append(f"Outcome: {outcome}")
        if effects:
            log.append(f"Effects triggered: {', '.join(effects)}")

    return {
        "outcome": outcome,
        "damage": margin if outcome.startswith("hit") else 0,
        "effects": effects,
        "log": log,
        "notes": []
    }