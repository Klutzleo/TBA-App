# routes/combat.py

from flask import Blueprint, request, jsonify

from backend.roll_logic import resolve_combat_roll, simulate_combat
from backend.magic_logic import cast_spell, character_from_dict

from flask_smorest import Blueprint

combat_blp = Blueprint(
    "Combat",
    "combat",
    url_prefix="/api/combat",
    description="Combat resolution and simulation"
)

@combat_blp.route("/roll/combat", methods=["POST"])
@swag_from("docs/roll_combat.yml")
def post_roll_combat():
    try:
        data       = request.get_json()
        attacker   = data.get("attacker", {})
        defender   = data.get("defender", {})
        weapon_die = data.get("weapon_die", "1d8")
        defense_die= data.get("defense_die", "1d6")
        bap        = data.get("bap", False)

        result = resolve_combat_roll(attacker, defender, weapon_die, defense_die, bap)
        return jsonify(result)
    except Exception as e:
        print("Combat roll error:", str(e))
        return jsonify({"error": "Combat roll failed"}), 500

@combat_blp.route("/roll/combat/simulate", methods=["POST"])
@swag_from("docs/simulate.yml")
def post_roll_combat_simulate():
    try:
        data       = request.get_json()
        attacker   = data.get("attacker", {})
        defender   = data.get("defender", {})
        weapon_die = data.get("weapon_die", "1d8")
        defense_die= data.get("defense_die", "1d6")
        bap        = data.get("bap", False)

        result = simulate_combat(attacker, defender, weapon_die, defense_die, bap)
        return jsonify(result)
    except Exception as e:
        print("Combat simulation error:", str(e))
        return jsonify({"error": "Simulation failed"}), 500

# ─────────────── New Magic Endpoint ───────────────

@combat_blp.route("/magic/cast", methods=["POST"])
@swag_from("docs/cast_spell.yml")
def post_cast_spell():
    try:
        payload   = request.get_json()
        # Build Character instances from JSON
        caster    = character_from_dict(payload["caster"])
        targets   = [character_from_dict(t) for t in payload.get("targets", [])]
        slot      = payload["slot"]
        bap_trig  = payload.get("bap", False)
        new_enc   = payload.get("new_encounter", False)

        if new_enc:
            caster.reset_casts()

        # Perform the spell‐cast
        entry = cast_spell(
            caster=caster,
            targets=targets,
            slot=slot,
            bap_triggered=bap_trig
        )

        # (Optionally) persist entry in your DB here
        # save_battle_log(payload["session_id"], entry)

        return jsonify(entry)
    except Exception as e:
        print("Magic cast error:", str(e))
        return jsonify({"error": "Magic cast failed"}), 500