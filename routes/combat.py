# routes/combat.py

from flask import Blueprint, request, jsonify
from flasgger import swag_from
from backend.roll_logic import resolve_combat_roll, simulate_combat

combat_bp = Blueprint("combat", __name__)

@combat_bp.route("/roll/combat", methods=["POST"])
@swag_from("docs/roll_combat.yml")
def post_roll_combat():
    try:
        data = request.get_json()
        attacker = data.get("attacker", {})
        defender = data.get("defender", {})
        weapon_die = data.get("weapon_die", "1d8")
        defense_die = data.get("defense_die", "1d6")
        bap = data.get("bap", False)

        result = resolve_combat_roll(attacker, defender, weapon_die, defense_die, bap)
        return jsonify(result)
    except Exception as e:
        print("Combat roll error:", str(e))
        return jsonify({"error": "Combat roll failed"}), 500

@combat_bp.route("/roll/combat/simulate", methods=["POST"])
@swag_from("docs/simulate.yml")
def post_roll_combat_simulate():
    try:
        data = request.get_json()
        attacker = data.get("attacker", {})
        defender = data.get("defender", {})
        weapon_die = data.get("weapon_die", "1d8")
        defense_die = data.get("defense_die", "1d6")
        bap = data.get("bap", False)
        max_rounds = data.get("max_rounds", 5)

        result = simulate_combat(attacker, defender, weapon_die, defense_die, bap, max_rounds)
        return jsonify(result)
    except Exception as e:
        print("Combat simulation error:", str(e))
        return jsonify({"error": "Simulation failed"}), 500