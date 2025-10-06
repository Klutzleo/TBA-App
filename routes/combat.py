from flask import request
from flask_smorest import Blueprint
from backend.roll_logic import resolve_combat_roll, simulate_combat
from backend.magic_logic import cast_spell, character_from_dict

combat_blp = Blueprint(
    "Combat",
    "combat",
    url_prefix="/api/combat",
    description="Combat resolution and simulation"
)

from schemas.combat import CombatRollRequest, CombatRollResponse

@combat_blp.route("/roll/combat", methods=["POST"])
@combat_blp.arguments(CombatRollRequest)
@combat_blp.response(200, CombatRollResponse)
@combat_blp.alt_response(400, description="Missing or invalid input")
@combat_blp.alt_response(500, description="Internal server error")
def post_roll_combat(payload):
    try:
        result = resolve_combat_roll(**payload)
        return result
    except Exception as e:
        print("Combat roll error:", str(e))
        return {"error": "Combat roll failed"}, 500

@combat_blp.route("/roll/combat/simulate", methods=["POST"])
@combat_blp.response(200)
@combat_blp.alt_response(400, description="Missing or invalid input")
@combat_blp.alt_response(500, description="Internal server error")
def post_roll_combat_simulate():
    try:
        data = request.get_json()
        attacker = data.get("attacker", {})
        defender = data.get("defender", {})
        weapon_die = data.get("weapon_die", "1d8")
        defense_die = data.get("defense_die", "1d6")
        bap = data.get("bap", False)

        result = simulate_combat(attacker, defender, weapon_die, defense_die, bap)
        return result
    except Exception as e:
        print("Combat simulation error:", str(e))
        return {"error": "Simulation failed"}, 500

